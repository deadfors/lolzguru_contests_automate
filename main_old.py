import base64
import json
import re
import time
import datetime
import os

import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.firefox.options import Options as FireFoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from bs4 import BeautifulSoup
import pytesseract
from PIL import Image, UnidentifiedImageError

import telegram_listener

PARTICIPATE_BUTTON_XPATH = "//a[@class='button marginBlock LztContest--Participate']"
LIKE_BUTTON_XPATH = "//span[@class='icon likeCounterIcon']"
CAPTCHA_INPUT_FIELD_XPATH = "//input[@name='captcha_question_answer']"

LOGIN_INPUT_FIELD_ID = "ctrl_pageLogin_login"
PASSWORD_INPUT_FIELD_ID = "ctrl_pageLogin_password"
LOGIN_BUTTON_XPATH = "//input[@type='submit']"

TELEGRAM_INPUT_FIELD_ID = "ctrl_telegram_code"
TELEGRAM_BUTTON_CONFIRM_XPATH = "//input[@type='submit']"

IMAGE_AVATAR_XPATH = "//img[@class='navTab--visitorAvatar']"
FILTER_FLAG_AVAILABLE_CONTESTS_BUTTON_XPATH = "//i[@class='far fa-flag muted']"

CONTESTS_TITLE_TEXT_XPATH = "//h1[@title='Розыгрыши']"
NOT_FOUND_PAGE_XPATH = "//label[@class='OverlayCloser']"


def load_data_from_file():
    result = {}
    try:
        if not os.path.exists('data.txt'):
            with open('data.txt', 'w') as f:
                f.write('{ "username":"", "password":"", "api_id":"", "api_hash":""}')

        with open('data.txt') as json_file:
            data = json.load(json_file)

        if 'username' in data:
            result['username'] = data['username']
        if 'password' in data:
            result['password'] = data['password']
        if 'api_id' in data:
            result['api_id'] = data['api_id']
        if 'api_hash' in data:
            result['api_hash'] = data['api_hash']

    except KeyError as error:
        print('Cannot find: %s', error.args[0])
    else:
        return result['username'], result['password'], result['api_id'], result['api_hash']


def get_current_time():
    return '_'.join(datetime.datetime.now().strftime("%H:%M:%S").split(':'))


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
        try:
            # Open image
            image_to_crop = Image.open(self.captcha_image_filename, 'r')
            # Crop image
            image = image_to_crop.crop((-1, 8, 65, 22))
            # Save image
            image.save(self.cropped_captcha_filename)
        except UnidentifiedImageError as error:
            print(error)

    def change_image_pixels(self):
        """
        Change pixels to black or white.
        If pixel RGB(32, 32, 32) close to black change to  RGB(0, 0, 0).
        :return:
        """
        try:
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
        except UnidentifiedImageError as error:
            print(error)

    def image_to_string(self):
        """
        Recognize text on image than convert to string via pytesseract library.
        :return: Recognized string
        """
        img = Image.open(self.cropped_captcha_filename)
        config = '--psm 10 --oem 1 -c tessedit_char_whitelist=0123456789+?'
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
        self.login_url = 'https://lolz.guru/login'
        self.contests_url = 'https://lolz.guru/forums/contests/page-2'
        self.links = []
        self.session = requests.Session()

    def login(self):
        """
        Login to lolz account.
        :return:
        """
        self.driver.get(self.login_url)
        # Set username field
        print('Trying to login!')
        login_input = self._wait_element_visible_ID(LOGIN_INPUT_FIELD_ID)
        time.sleep(2)
        self.driver.set_window_size(width=510, height=730)
        login_input.send_keys(USERNAME)

        # Set password field
        password_input = self._wait_element_visible_ID(PASSWORD_INPUT_FIELD_ID)
        password_input.send_keys(PASSWORD)

        # Get and click login button
        self._wait_element_visible_XPATH(LOGIN_BUTTON_XPATH)
        self.driver.execute_script("document.querySelector('.button.primary.large.full').click();")

        # Get telegram message and confirm
        '''
        time.sleep(5)
        telegram_code = telegram_listener.get_last_message()
     
        telegram_input = self._wait_element_visible_ID(TELEGRAM_INPUT_FIELD_ID)
        telegram_input.send_keys(telegram_code)

        confirm_button = self._wait_element_visible_XPATH(TELEGRAM_BUTTON_CONFIRM_XPATH)
        confirm_button.click()'''

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
            self.driver.save_screenshot(f'nudes/ID/{str(get_current_time())}_ID.png')
            self.driver.quit()
            print(exception)

    def _wait_element_visible_XPATH(self, xpath: str, wait_time=20):
        """
        Wait for element is visible on page by XPATH
        :param xpath:
        :return:
        """
        try:
            return WebDriverWait(self.driver, wait_time).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
        except TimeoutException as error:
            self.driver.save_screenshot(f'nudes/XPATH/{str(get_current_time())}_XPATH.png')
            # self.driver.quit()
            print(error)

    def _click_participate(self):
        try:
            self.driver.execute_script(
                "document.querySelector('.button.marginBlock.LztContest--Participate').click();")
        except Exception as error:
            print(error)

    def _click_like(self, class_name):
        try:
            self.driver.execute_script(f"document.querySelector('{class_name}').click();")
        except Exception as error:
            print(error)

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
        request_cookies_browser = self.driver.get_cookies()
        c = [self.session.cookies.set(c['name'], c['value']) for c in request_cookies_browser]

        while True:
            self.links = self.get_contests_urls()
            print(f"{get_current_time()}| Available contests: {self.links}")

            for link in self.links:
                self.driver.get(f'https://lolz.guru/{link}')
                '''if self._wait_element_visible_XPATH(NOT_FOUND_PAGE_XPATH, wait_time=2):
                    print('Запрашиваемая тема не найдена.')
                    continue'''

                print('Trying to get captcha image from page.')
                image_in_base64 = self.get_image_from_page()
                if image_in_base64 == '':
                    continue
                captcha_text = self.ImageWorker.process_image(image_in_base64)

                print('Trying to solve captcha.')
                captcha_result = self.parse_captcha_string(captcha_text)
                print(f"Captcha: {str(captcha_text)} = {str(captcha_result)}")
                if captcha_result is None:
                    print('Can`t recognize captcha.')
                    continue

                input_captcha_field = self._wait_element_visible_XPATH(CAPTCHA_INPUT_FIELD_XPATH)
                input_captcha_field.send_keys(captcha_result)
                self._click_participate()
                time.sleep(0.5)
                self._click_like('.LikeLink.item.control.like')
                time.sleep(0.5)
                self._click_like('.Tooltip.PopupTooltip.LikeLink.item.control.like')
            time.sleep(5)

    @staticmethod
    def parse_captcha_string(captcha_string: str):
        """
        Get captcha string. Get two digits from string and
        :param captcha_string:
        :return: sum of numbers -> int
        """
        try:
            if captcha_string.find('?') != -1:
                captcha_string = captcha_string[:captcha_string.find('?')]
            print(captcha_string)
            list_digits = captcha_string.split('+')
            if list_digits[1] == '':
                return None

        except (ValueError, IndexError) as error:
            print('Cant recognize captcha')
            print(error)
        else:
            return int(list_digits[0]) + int(list_digits[1])

    def get_image_from_page(self) -> str:
        """
        Get image from page in base64 format.
        :return: string base64
        """
        try:
            html_page_source = self.driver.page_source
            html_parse_bs = BeautifulSoup(html_page_source, 'html.parser')
            items = html_parse_bs.select('div[class="ddText"]')
            result_items = re.findall(r'\"data:image.*\"', str(items[0]))
            result_items = str(result_items).replace("\"", "")
        except IndexError as error:
            print(error)
        else:
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
        _links = []
        page_bs = ''
        try:
            html_source_page = self.session.get(self.contests_url).text

            page_bs = BeautifulSoup(html_source_page, 'html.parser')
        except Exception as e:
            print(e)

        try:
            for item in page_bs.find_all('a', class_='listBlock main PreviewTooltip'):
                if 'alreadyParticipate' not in str(item) \
                    and 'moderated fa fa-eye-slash' not in str(item) \
                        and 'fa fa-bullseye mainc Tooltip' not in str(item):
                    _links.append(item.get('href'))
        except Exception as error:
            self.driver.quit()
            raise error
        else:
            return _links

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.system("TASKKILL /F /IM firefox.exe")
        os.system("TASKKILL /F /IM geckodriver.exe")
        self.driver.close()
        self.driver.quit()

    def __enter__(self):
        driver_options = FireFoxOptions()
        driver_options.add_argument('--headless')

        profile = webdriver.FirefoxProfile()
        profile.set_preference("permissions.default.image", 2)
        profile.set_preference("browser.cache.disk.enable", 2)
        profile.set_preference("browser.cache.memory.enable", 2)
        profile.set_preference("browser.cache.offline.enable", 2)
        profile.set_preference("network.http.use-cache", 2)

        self.driver = webdriver.Firefox(profile, executable_path=r"geckodriver.exe", options=driver_options)
        self.ImageWorker = ImageWorker()

        return self


if __name__ == '__main__':
    if not os.path.exists('./nudes'):
        os.makedirs('nudes')
        os.makedirs('nudes/ID')
        os.makedirs('nudes/XPATH')
        os.makedirs('nudes/get_image_from_page')
        os.makedirs('nudes/participate_button')
        os.makedirs('nudes/Exception')
        os.makedirs('nudes/LIKE')

    # telegram_listener.client.start()
    USERNAME, PASSWORD, _, _ = load_data_from_file()

    with LolzWorker() as lolz:
        lolz.login()
        lolz.participate_in_contests()
