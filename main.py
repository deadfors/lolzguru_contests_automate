import base64
import re
import time

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from bs4 import BeautifulSoup
import pytesseract
from PIL import Image

import telegram_listener
from userdata import USERNAME, PASSWORD

PARTICIPATE_BUTTON_XPATH = "//a[@class='button marginBlock LztContest--Participate']"
LIKE_BUTTON_XPATH = "//div[@class='LikeLabel']"
CAPTCHA_INPUT_FIELD_XPATH = "//input[@name='captcha_question_answer']"

LOGIN_INPUT_FIELD_ID = "ctrl_pageLogin_login"
PASSWORD_INPUT_FIELD_ID = "ctrl_pageLogin_password"
LOGIN_BUTTON_XPATH = "//input[@type='submit']"

TELEGRAM_INPUT_FIELD_ID = "ctrl_telegram_code"
TELEGRAM_BUTTON_CONFIRM_XPATH = "//input[@type='submit']"

IMAGE_AVATAR_XPATH = "//img[@class='navTab--visitorAvatar']"
FILTER_FLAG_AVAILABLE_CONTESTS_BUTTON_XPATH = "//i[@class='far fa-flag muted']"

CONTESTS_TITLE_TEXT_XPATH = "//h1[@title='Розыгрыши']"

PYTESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract'


class ImageWorker:
    """
    Working with captcha image.
    """

    def __init__(self):
        """Constructor"""
        self.captcha_image_filename = 'captcha_image.jpg'
        self.cropped_captcha_filename = 'cropped_captcha.jpg'

    def convert_base64_to_image(self, image_in_base64):
        """
        Convert base64 string to image file.
        :param image_in_base64:
        :return:
        """
        image_in_base64 = str(image_in_base64).replace('data:image/jpeg;base64,', '')
        image_data = base64.b64decode(image_in_base64)

        # Save image as image file
        with open(self.captcha_image_filename, 'wb') as file:
            file.write(image_data)

    def corp_image(self):
        """
        Crop and save image.
        :return:
        """
        # Open image
        image_to_crop = Image.open(self.captcha_image_filename, 'r')
        # Crop image
        image = image_to_crop.crop((-1, 8, 65, 22))
        # Save image
        image.save(self.cropped_captcha_filename)

    def change_image_pixels(self):
        """
        Change pixels to black or white.
        If pixel RGB(32, 32, 32) close to black change to  RGB(0, 0, 0).
        :return:
        """
        image = Image.open(self.cropped_captcha_filename, 'r')
        pixels = list(image.getdata())
        new_pixels_list = []
        for rgb in pixels:
            if rgb[0] < 160:
                rgb = (0, 0, 0)
            if rgb[0] > 160:
                rgb = (255, 255, 255)
            new_pixels_list.append(rgb)
        image.putdata(new_pixels_list)
        image.save(self.cropped_captcha_filename)

    def image_to_string(self):
        """
        Recognize text on image than convert to string via pytesseract library.
        :return: Recognized string
        """
        img = Image.open(self.cropped_captcha_filename)
        config = '--psm 10 --oem 1 -c tessedit_char_whitelist=0123456789+?'
        pytesseract.pytesseract.tesseract_cmd = PYTESSERACT_PATH
        return pytesseract.image_to_string(img, config=config)

    def process_image(self, base64_string: str) -> str:
        """
        Convert and get tex from image.
        :param base64_string:
        :return:
        """
        self.convert_base64_to_image(base64_string)
        self.corp_image()
        self.change_image_pixels()
        return self.image_to_string()


class LolzWorker:
    """
    Lolz.guru worker. Auto participate in contests.
    """

    def __init__(self):
        """
        Constructor.
        """
        driver_options = Options()
        driver_options.add_argument('--headless')
        driver_options.add_argument('--disable-gpu')
        self.driver = webdriver.Chrome(r'.\chromedriver.exe', options=driver_options)
        self.login_url = 'https://lolz.guru/login'
        self.contests_url = 'https://lolz.guru/forums/contests/'
        self.links = []
        self.ImageWorker = ImageWorker()

    def login(self):
        """
        Login to lolz account.
        :return:
        """
        self.driver.get(self.login_url)
        # Set username field
        print('Trying to login!')
        login_input = self._wait_element_visible_ID(LOGIN_INPUT_FIELD_ID)
        login_input.send_keys(USERNAME)

        # Set password field
        password_input = self._wait_element_visible_ID(PASSWORD_INPUT_FIELD_ID)
        password_input.send_keys(PASSWORD)

        # Get and click login button
        login_button = self._wait_element_visible_XPATH(LOGIN_BUTTON_XPATH)
        login_button.click()

        # Get telegram message and confirm
        time.sleep(2)
        telegram_code = telegram_listener.get_last_message()

        telegram_input = self._wait_element_visible_ID(TELEGRAM_INPUT_FIELD_ID)
        telegram_input.send_keys(telegram_code)

        confirm_button = self._wait_element_visible_XPATH(TELEGRAM_BUTTON_CONFIRM_XPATH)
        confirm_button.click()

    def _wait_element_visible_ID(self, element_id):
        """
        Wait for element is visible on page by ID
        :param element_id:
        :return:
        """
        try:
            return WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, element_id))
            )
        except TimeoutException as exception:
            self.driver.save_screenshot("screenshot.png")
            self.driver.quit()
            raise exception

    def _wait_element_visible_XPATH(self, xpath: str):
        """
        Wait for element is visible on page by XPATH
        :param xpath:
        :return:
        """
        try:
            return WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
        except TimeoutException as exception:
            self.driver.save_screenshot("screenshot.png")
            self.driver.quit()
            raise exception

    def like_contest(self):
        """
        Like contest.
        """
        try:
            like_contest = self._wait_element_visible_XPATH(LIKE_BUTTON_XPATH)
            like_contest.click()
        except ElementNotInteractableException as exception:
            self.driver.save_screenshot("screenshot.png")
            print('Can`t like')
            print(exception)

    def participate_in_contests(self):
        """
        Participate in contests.
        Get urls from page than open one by one.
        :return:
        """
        # Wait for page load and set ony available contests on page
        self._wait_element_visible_XPATH(IMAGE_AVATAR_XPATH)
        self.driver.get(self.contests_url)
        self._set_only_available_contests()

        while True:
            time.sleep(2)
            self.links = self.get_contests_urls()
            time.sleep(2)
            print(f"Available contests: {self.links}")

            for link in self.links:
                self.driver.get(f'https://lolz.guru/{link}')
                self._wait_element_visible_XPATH(PARTICIPATE_BUTTON_XPATH)
                print('Trying to get captcha image from page.')
                image_in_base64 = self.get_image_from_page()
                captcha_text = self.ImageWorker.process_image(image_in_base64)

                print('Trying to solve captcha.')
                captcha_result = self._parse_captcha_string(captcha_text)
                print(f"Captcha: {captcha_text} = {captcha_result}")
                if captcha_result is None:
                    continue

                input_captcha_field = self._wait_element_visible_XPATH(CAPTCHA_INPUT_FIELD_XPATH)
                input_captcha_field.send_keys(captcha_result)

                participate_button = self._wait_element_visible_XPATH(PARTICIPATE_BUTTON_XPATH)
                actions = ActionChains(self.driver)
                actions.move_to_element(participate_button).perform()
                time.sleep(1)
                #  You can comment this line if you want.
                self.like_contest()
                participate_button.click()


            time.sleep(10)

    def _parse_captcha_string(self, captcha_string: str) -> int:
        """
        Get captcha string. Get two digits from string and
        :param captcha_string:
        :return: sum of numbers -> int
        """
        try:
            if captcha_string[-1].isdigit() and captcha_string[-2] == '?':
                captcha_string = captcha_string[:-1]
            captcha_string = captcha_string.replace('?', '')
            print(captcha_string)
            list_digits = captcha_string.split('+')
            print(list_digits)
        except (ValueError, IndexError) as exception:
            self.driver.save_screenshot("screenshot.png")
            print('Cant recognize captcha')
            print(exception)
        else:
            return int(list_digits[0]) + int(list_digits[1])

    def get_image_from_page(self) -> str:
        """
        Get image from page in base64 format.
        :return: string base64
        """
        html_page_source = self.driver.page_source
        html_parse_bs = BeautifulSoup(html_page_source, 'html.parser')
        items = html_parse_bs.select('div[class="ddText"]')
        result_items = re.findall(r'\"data:image.*\"', str(items[0]))
        result_items = str(result_items).replace("\"", "")
        return result_items

    def _set_only_available_contests(self):
        """
        Set flag available contest on page.
        :return:
        """
        available_button = self._wait_element_visible_XPATH(FILTER_FLAG_AVAILABLE_CONTESTS_BUTTON_XPATH)
        available_button.click()

    def get_contests_urls(self):
        """
        Get contests urls.
        :return:
        """
        self.driver.get(self.contests_url)
        _links = []
        time.sleep(2)
        self._wait_element_visible_XPATH(CONTESTS_TITLE_TEXT_XPATH)
        html_source_page = self.driver.page_source
        page_bs = BeautifulSoup(html_source_page, 'html.parser')

        try:
            for item in page_bs.find_all('a', class_='listBlock main PreviewTooltip'):
                if 'alreadyParticipate' not in str(item):
                    _links.append(item.get('href'))
        except Exception as exception:
            self.driver.quit()
            raise exception
        else:
            return _links


if __name__ == '__main__':
    telegram_listener.client.start()

    try:
        lolz = LolzWorker()
        lolz.login()
        lolz.participate_in_contests()
    except KeyboardInterrupt as exception:
        print('BB')
