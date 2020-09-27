import base64
import json
import re
import time
import datetime
import os
import requests

from bs4 import BeautifulSoup
import pytesseract
from PIL import Image, UnidentifiedImageError
from requests import RequestException

def load_data_from_file():
    result = {}
    try:
        if not os.path.exists('data.txt'):
            with open('data.txt', 'w') as f:
                f.write('{ "username":"", "password":"", "cookie":"" }')

        with open('data.txt') as json_file:
            data = json.load(json_file)

        if 'username' in data:
            result['username'] = data['username']
        if 'password' in data:
            result['password'] = data['password']
        if 'cookie' in data:
            result['cookie'] = data['cookie']
    except KeyError as error:
        print('Cannot find: %s', error.args[0])
    else:
        return result


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
        self.contests_url = 'https://lolz.guru/forums/contests/'
        self.links = []
        self.session = requests.Session()
        self.ImageWorker = ImageWorker()
        self.headers = {'cookie': COOKIE}
        self.token = None

    def is_login(self):
        """
        Check is user login
        :return:
        """
        req = self.session.get('https://lolz.guru/', headers=self.headers)
        req_bs = BeautifulSoup(req.text, 'html.parser')
        if not req_bs.select('img[class=navTab--visitorAvatar]'):
            return False
        return True

    def login(self):
        """
        Login lolz
        :return:
        """
        try:
            data = {
                'login': USERNAME,
                'password': PASSWORD,
                'remember': 1,
                'stopfuckingbrute1337': 1,
                'cookie_check': 1,
                '_xfToken': '',
                'redirect': 'https://lolz.guru/'
            }
            self.session.post(self.login_url, data=data, headers=self.headers)
        except RequestException as e:
            raise e

    def get_xftoken(self) -> str:
        """
        Parse page and get xfToken
        :return:
        """
        try:
            r_auth = self.session.get(self.contests_url, headers=self.headers)
            token_bs = BeautifulSoup(r_auth.text, 'html.parser')
            token = token_bs.select('input[name=_xfToken]')[0]['value']
        except RequestException as e:
            raise e
        else:
            return token

    def get_captcha_image(self, page_html) -> str:
        """
        Parse page and get captcha
        :param page_html:
        :return:
        """
        try:
            items = page_html.select('div[class="ddText"]')
            result_items = re.findall(r'\"data:image.*\"', str(items[0]))
            result_items = str(result_items).replace("\"", "")
        except Exception as e:
            raise e
        else:
            return result_items

    def get_captcha_hash(self, page_html) -> str:
        try:
            captcha_hash = page_html.select('input[name="captcha_question_hash"]')[0]['value']
        except IndexError as e:
            raise e
        else:
            return captcha_hash

    def get_post_id(self, page_html) -> str:
        try:
            item = page_html.find_all('a', class_='item messageDateInBottom datePermalink hashPermalink '
                                                  'OverlayTrigger muted')[0]
            post_id = item.get('data-href')
            return post_id.split('/')[1]
        except IndexError as e:
            raise e

    def like_contest(self, thread_page, post_id):
        try:
            url = f'https://lolz.guru/posts/{post_id}/like'
            data = {
                '_xfRequestUri': f'/threads/{thread_page}/',
                '_xfNoRedirect': 1,
                '_xfToken': self.token,
                '_xfResponseType': 'json',
            }

            self.session.post(url, data=data, headers=self.headers)
        except RequestException as e:
            raise e

    def participate_in_contests(self):
        """
        Participate in contests.
        Get urls from page than open one by one.
        :return:
        """
        self.token = self.get_xftoken()

        while True:
            self.links = self.get_contests_urls()
            
            if self.links:
                print(f"{get_current_time()}| Available contests: {self.links}")

            for link in self.links:
                print(f'https://lolz.guru/{link}')
                link = link.replace('unread', '')
                if not self.check_page(link=link):
                    continue

                with self.session.get(f'https://lolz.guru/{link}', headers=self.headers) as page_req:
                    html_parse_bs = BeautifulSoup(page_req.text, 'html.parser')
                    captcha_in_base64 = self.get_captcha_image(html_parse_bs)
                    captcha_hash = self.get_captcha_hash(html_parse_bs)
                    #post_id = self.get_post_id(html_parse_bs)

                print('Trying to solve captcha')
                captcha_text = self.ImageWorker.process_image(captcha_in_base64)
                captcha_result = self.parse_captcha_string(captcha_text)
                print(f'Captcha: {str(captcha_text)} = {str(captcha_result)}')

                if captcha_result is None:
                    print('Can`t recognize captcha.')
                    continue

                data = {
                    'captcha_question_answer': captcha_result,
                    'captcha_question_hash': captcha_hash,
                    '_xfRequestUri': link,
                    '_xfNoRedirect': 1,
                    '_xfToken': self.token,
                    '_xfResponseType': 'json',
                }
                req = self.session.post(f'https://lolz.guru/{link}participate', data=data, headers=self.headers).json()

                if '_redirectStatus' in req:
                    print(f'Status: {req["_redirectStatus"]}')
                    self.like_contest(thread_page=link.replace('threads/', ''), post_id=post_id)
                else:
                    print(f'Status: {req["error"]}')

                print('_' * 50)
            time.sleep(1)

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
            if int(list_digits[1]) > 25:
                list_digits[1] = list_digits[1][0]

        except (ValueError, IndexError) as error:
            print('Cant recognize captcha')
            print(error)
        else:
            return int(list_digits[0]) + int(list_digits[1])

    def get_contests_urls(self):
        """
        Get contests urls.
        :return:
        """
        _links = []
        page_bs = ''
        try:
            html_source_page = self.session.get('https://lolz.guru/forums/contests/', headers=self.headers).text
            html_source_page2 = self.session.get('https://lolz.guru/forums/contests/page-2', headers=self.headers).text
            html_source_page = html_source_page + html_source_page2
            page_bs = BeautifulSoup(html_source_page, 'html.parser')
        except RequestException as e:
            print(e)

        try:
            for item in page_bs.find_all('a', class_='listBlock main PreviewTooltip'):
                if 'alreadyParticipate' not in str(item) \
                    and 'moderated fa fa-eye-slash' not in str(item) \
                        and 'fa fa-bullseye mainc Tooltip' not in str(item):
                    _links.append(item.get('href'))
        except Exception as error:
            print(error)
            return None
        else:
            return _links

    def check_page(self, link):
        html_page_source = self.session.get('https://lolz.guru/' + link, headers=self.headers).text
        if 'error mn-15-0-0' in html_page_source:
            print('Набор участников для розыгрыша завершен.')
            return False
        elif 'OverlayCloser' in html_page_source:
            print('Запрашиваемая тема не найдена.')
            return False
        return True


if __name__ == '__main__':
    COOKIE = [item for item in load_data_from_file().values()][0]

    lolz = LolzWorker()
    #lolz.login()
    if lolz.is_login():
        print('Login successful')
        lolz.participate_in_contests()
    else:
        print('Login fail')
