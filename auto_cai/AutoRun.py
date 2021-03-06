# -*- coding: utf-8 -*-

import os
import sys
import yaml
import time
import copy
import json
import tempfile
import shutil
import random
import urllib2
import xmltodict
from xlrd import open_workbook
import logging
from logging.handlers import RotatingFileHandler
from selenium import webdriver
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support.expected_conditions import presence_of_element_located, visibility_of_element_located
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary


CONFIGFILE = 'config.yaml'
DATA = 'data.xlsx'
UA_FILE = 'UA.txt'
PROXY_SHEET = 'proxy'
ACTIONS = ['click', 'clear', 'sendkeys', 'submit', 'select', 'readonly_input']

WEBDRIVER_PREFERENCES = """
{
  "frozen": {
    "app.update.auto": false,
    "app.update.enabled": false,
    "browser.displayedE10SNotice": 4,
    "browser.download.manager.showWhenStarting": false,
    "browser.EULA.override": true,
    "browser.EULA.3.accepted": true,
    "browser.link.open_external": 2,
    "browser.link.open_newwindow": 2,
    "browser.offline": false,
    "browser.reader.detectedFirstArticle": true,
    "browser.safebrowsing.enabled": false,
    "browser.safebrowsing.malware.enabled": false,
    "browser.search.update": false,
    "browser.selfsupport.url" : "",
    "browser.sessionstore.resume_from_crash": false,
    "browser.shell.checkDefaultBrowser": false,
    "browser.tabs.warnOnClose": false,
    "browser.tabs.warnOnOpen": false,
    "datareporting.healthreport.service.enabled": false,
    "datareporting.healthreport.uploadEnabled": false,
    "datareporting.healthreport.service.firstRun": false,
    "datareporting.healthreport.logging.consoleEnabled": false,
    "datareporting.policy.dataSubmissionEnabled": false,
    "datareporting.policy.dataSubmissionPolicyAccepted": false,
    "devtools.errorconsole.enabled": true,
    "dom.disable_open_during_load": false,
    "extensions.autoDisableScopes": 10,
    "extensions.blocklist.enabled": false,
    "extensions.checkCompatibility.nightly": false,
    "extensions.logging.enabled": true,
    "extensions.update.enabled": false,
    "extensions.update.notifyUser": false,
    "javascript.enabled": true,
    "network.manage-offline-status": false,
    "network.http.phishy-userpass-length": 255,
    "offline-apps.allow_by_default": true,
    "prompts.tab_modal.enabled": false,
    "security.csp.enable": false,
    "security.fileuri.origin_policy": 3,
    "security.fileuri.strict_origin_policy": false,
    "security.warn_entering_secure": false,
    "security.warn_entering_secure.show_once": false,
    "security.warn_entering_weak": false,
    "security.warn_entering_weak.show_once": false,
    "security.warn_leaving_secure": false,
    "security.warn_leaving_secure.show_once": false,
    "security.warn_submit_insecure": false,
    "security.warn_viewing_mixed": false,
    "security.warn_viewing_mixed.show_once": false,
    "signon.rememberSignons": false,
    "toolkit.networkmanager.disable": true,
    "toolkit.telemetry.prompted": 2,
    "toolkit.telemetry.enabled": false,
    "toolkit.telemetry.rejected": true,
    "xpinstall.signatures.required": false,
    "xpinstall.whitelist.required": false
  },
  "mutable": {
    "browser.dom.window.dump.enabled": true,
    "browser.laterrun.enabled": false,
    "browser.newtab.url": "about:blank",
    "browser.newtabpage.enabled": false,
    "browser.startup.page": 0,
    "browser.startup.homepage": "about:blank",
    "browser.usedOnWindows10.introURL": "about:blank",
    "dom.max_chrome_script_run_time": 30,
    "dom.max_script_run_time": 30,
    "dom.report_all_js_exceptions": true,
    "javascript.options.showInConsole": true,
    "network.http.max-connections-per-server": 10,
    "startup.homepage_welcome_url": "about:blank",
    "startup.homepage_welcome_url.additional": "about:blank",
    "webdriver_accept_untrusted_certs": true,
    "webdriver_assume_untrusted_issuer": true
  }
}
"""


# ---------------------------------------------------------
#                          工具类
# ---------------------------------------------------------


class Logger(object):
    """自定义日志类，读取配置，并以配置为准进行日志输出，分别到console和log file里。
        methods:
            __init__(logger_name='root')
                读入配置文件，进行配置。logger_name默认为root。
            get_logger()
                读取配置，添加相应handler，返回logger。
    """
    def __init__(self, logger_name='root', console_level='DEBUG', file_level='DEBUG'):
        self.logger = logging.getLogger(logger_name)
        logging.root.setLevel(logging.NOTSET)
        self.log_file_name = 'AutoRun.log'
        self.console_log_level = console_level
        self.file_log_level = file_level
        self.console_output = True
        self.file_output = True
        self.formatter = logging.Formatter('%(asctime)s %(message)s')

    def get_logger(self):
        """在logger中添加日志句柄并返回，如果logger已有句柄，则直接返回"""
        if not self.logger.handlers:  # 避免重复日志
            if self.console_output:
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(self.formatter)
                console_handler.setLevel(self.console_log_level)
                self.logger.addHandler(console_handler)
            else:
                pass
            if self.file_output:
                file_handler = RotatingFileHandler(os.path.abspath(self.log_file_name))
                file_handler.setFormatter(self.formatter)
                file_handler.setLevel(self.file_log_level)
                self.logger.addHandler(file_handler)
            else:
                pass
        return self.logger

# add program logger and selenium logger
logger = Logger().get_logger()
selenium_logger = Logger('selenium.webdriver.remote.remote_connection', console_level='ERROR', file_level='ERROR').get_logger()


class ExcelReader(object):
    """ read excel file """
    def __init__(self, sheet):
        self.book_name = os.path.abspath(DATA)
        self.sheet_locator = sheet
        self.book = self._book()
        self.sheet = self._sheet()

    def _book(self):
        try:
            return open_workbook(self.book_name)
        except IOError as e:
            logger.error(u'[Error] 打开excel出错')
            logger.exception(e)
            os._exit(0)

    def _sheet(self):
        """ Return sheet """
        try:
            return self.book.sheet_by_name(self.sheet_locator)  # by name
        except Exception as e:
            logger.error(u'[Error] sheet {} 不存在'.format(self.sheet_locator))
            # logger.exception(e)
            os._exit(0)

    @property
    def title(self):
        """ First row is title. """
        try:
            return self.sheet.row_values(0)
        except IndexError as e:
            logger.error(u'[Error] sheet中没有数据')
            # logger.exception(e)

    @property
    def data(self):
        """ Return data in specified type: [{row1:row2},{row1:row3},{row1:row4}...] """
        sheet = self.sheet
        title = self.title
        data = list()
        # zip title and rows
        for col in range(1, sheet.nrows):
            s1 = sheet.row_values(col)
            s2 = [unicode(s).encode('utf-8') for s in s1]  # utf-8 encoding
            data.append(dict(zip(title, s2)))
        return data

    @property
    def nums(self):
        """ Return the number of cases. """
        return len(self.data)


class YamlReader:
    """ Read YAML file """
    def __init__(self):
        self.yaml = os.path.abspath(CONFIGFILE)

    @property
    def data(self):
        """ return format data """
        with open(self.yaml, 'r') as f:
            al = yaml.safe_load_all(f)
            y = [x for x in al]
            return y


class FirefoxProfile(webdriver.FirefoxProfile):
    """ Rewrite FirefoxProfile, to avoid 'No such file ... webdriver.xpi/pref.json' exception"""
    def __init__(self, profile_directory=None):
        if not FirefoxProfile.DEFAULT_PREFERENCES:
            FirefoxProfile.DEFAULT_PREFERENCES = json.loads(WEBDRIVER_PREFERENCES)

        self.default_preferences = copy.deepcopy(
            FirefoxProfile.DEFAULT_PREFERENCES['mutable'])
        self.native_events_enabled = True
        self.profile_dir = profile_directory
        self.tempfolder = None
        if self.profile_dir is None:
            self.profile_dir = self._create_tempfolder()
        else:
            self.tempfolder = tempfile.mkdtemp()
            newprof = os.path.join(self.tempfolder, "webdriver-py-profilecopy")
            shutil.copytree(self.profile_dir, newprof,
                            ignore=shutil.ignore_patterns("parent.lock", "lock", ".parentlock"))
            self.profile_dir = newprof
            self._read_existing_userjs(os.path.join(self.profile_dir, "user.js"))
        self.extensionsDir = os.path.join(self.profile_dir, "extensions")
        self.userPrefs = os.path.join(self.profile_dir, "user.js")

    def update_preferences(self):
        for key, value in self.DEFAULT_PREFERENCES['frozen'].items():
            self.default_preferences[key] = value
        self._write_user_prefs(self.default_preferences)

    def add_extension(self, extension=os.path.abspath('webdriver.xpi')):
        self._install_extension(extension)

# ------------------------------------------------------------
# 上面工具类，下面是业务类
# ------------------------------------------------------------


class Config:
    """从config文件中读取配置，配置类"""
    browser = None
    location = None
    delay_submit = None
    wait_before_if = None
    random_agent = None
    proxytool = None
    ipchecker = None
    proxy = True

    def __init__(self, conf):
        Config.browser = conf['browser'].lower() if 'browser' in conf else 'firefox'
        Config.location = conf['location'] if 'location' in conf else None
        Config.delay_submit = conf['delay_submit'] if 'delay_submit' in conf else 5
        Config.wait_before_if = conf['if_wait'] if 'if_wait' in conf else 3
        Config.random_agent = conf['random_agent_spoofer'] if 'random_agent_spoofer' in conf else None
        Config.proxytool = conf['proxytool'] if 'proxytool' in conf else None
        Config.ipchecker = conf['ipchecker'] if 'ipchecker' in conf else 'http://173.230.146.56/ip/getip.php'
        Config.proxy = conf['proxy'] if 'proxy' in conf else True


# GET TASKS AND CONFIG
try:
    TASKS = YamlReader().data
    CONFIG = Config(TASKS.pop(0))
except Exception as e:
    logger.error(u'[Error] 读取配置文件出错')
    logger.exception(e)
    sys.exit(0)


class ProxyToolConfigException(Exception):
    pass


class Proxy:
    """代理类，用于检查IP，切换代理"""
    proxies = None
    num_proxy = None
    num_used = None
    country = None
    state = None

    def __init__(self):
        proxydata = ExcelReader(PROXY_SHEET)
        self.proxies = proxydata.data
        self.num_proxy = proxydata.nums

        self._proxy_log = os.path.abspath(PROXY_SHEET + '.log')
        self._used_nums()

        p = self.proxies[self.num_used]
        self.country = p['country']
        self.state = p['state']

    def change(self):
        """切换下一个代理"""
        if CONFIG.proxytool:
            if self.num_used >= self.num_proxy:
                logger.error(u'[Error] Excel中没有可用代理')
                raise ProxyToolConfigException()
            else:
                proxy = self.proxies[self.num_used]
                self.country = proxy['country']
                self.state = proxy['state']
                self.call_api()
        else:
            logger.error(u'[Error] 未配置proxytool路径，无法切换代理')
            raise ProxyToolConfigException()

    def call_api(self):
        """调用切换代理API"""
        if CONFIG.proxy and CONFIG.proxytool:
            logger.info(u'[Info] 调用代理 country: {0} state: {1}'.format(self.country, self.state))
            try:
                os.system(CONFIG.proxytool + ' -changeproxy/' + self.country + '/' + self.state)
                time.sleep(20)
            except:
                logger.error(u'[Error] 调用代理API失败')

    def _used_nums(self):
        """检查执行了多少个代理行"""
        if os.path.exists(self._proxy_log):
            with open(self._proxy_log, 'rb') as f:
                self.num_used = len(f.read())
        else:
            self.num_used = 0
        logger.info(u'[Info] 检测到已调用 {} 次代理API'.format(self.num_used))

    def log(self):
        """记录执行了一个代理行"""
        with open(self._proxy_log, 'a') as f:
            f.write('1')
            self.num_used += 1
            time.sleep(1)

    def check_ip(self):
        """检查当前IP对应country是否符合预期，使用同一个代理行切换6次，每次使用一个检查接口与两个备用接口，如果都失败，读取下一个代理行，继续检查"""
        check = False
        for i in range(10):
            check = self.checker()  # 检查接口
            if check:
                break
            else:
                check = self.backup_checker_1()  # 备用接口1
                if check:
                    break
                else:
                    check = self.backup_checker_2()  # 备用接口2
                    if check:
                        break
            if i <= 6:  # 使用同一个proxy切换7次
                logger.info(u'[Info] 重新切换代理')  # 如果没有成功，则切换当前行代理
                self.call_api()
            else:
                logger.error(u'[Error] 读取下一行代理数据')
                self.log()
                self.change()
        if check:
            return True
        else:
            logger.error(u'[Error] 10次检查均失败，退出程序！')
            sys.exit(0)  # todo 这里一个退出程序的口

    def _get(self, url=CONFIG.ipchecker):
        """访问接口并获取返回值"""
        try:
            time.sleep(2)
            return urllib2.urlopen(url).read()
        except:
            logger.error(u'[Error] 接口访问出错')

    def _check(self, country):
        """检查当前country是否符合预期"""
        if self.country == country:  # 检查country，如果当前country与预期一致则成功
            logger.info(u'[Info] 切换代理成功')
            return True
        else:
            logger.warning(u'[Warning] 实际country并非期望值')

    def checker(self):
        """默认接口检查IP，成功返回True，失败返回None"""
        ip_info_xml = self._get(CONFIG.ipchecker)
        if ip_info_xml:
            try:
                ip_info_dict = xmltodict.parse(ip_info_xml)
                ip = ip_info_dict['IpInfo']['ip']
                country = ip_info_dict['IpInfo']['country']
                region = ip_info_dict['IpInfo']['region']
                logger.info(u'[Info] 检查IP - IP: {0}  country: {1} region： {2}'.format(ip, country, region))
            except:
                logger.error(u'[Error] 接口返回的数据格式不正确')
            else:
                return self._check(country)

    def backup_checker_1(self):
        """备用接口1检查IP，成功返回True，失败返回None"""
        backup_url = 'http://freegeoip.net/xml/'
        ip_info_xml = self._get(backup_url)
        if ip_info_xml:
            try:
                ip_info_dict = xmltodict.parse(ip_info_xml)
                ip = ip_info_dict['Response']['IP']
                country = ip_info_dict['Response']['CountryCode']
                region = ip_info_dict['Response']['RegionCode']
                logger.info(u'[Info] 检查IP - IP: {0}  country: {1} region： {2}'.format(ip, country, region))
            except:
                logger.error(u'[Error] 接口返回的数据格式不正确')
            else:
                return self._check(country)

    def backup_checker_2(self):
        """备用接口2检查IP，成功返回True，失败返回None"""
        backup_url = 'http://ip-api.com/json'
        ip_info_str = self._get(backup_url)
        if ip_info_str:
            try:
                ip_info_json = json.loads(ip_info_str)
                ip = ip_info_json['query']
                country = ip_info_json['countryCode']
                region = ip_info_json['region']
                logger.info(u'[Info] 检查IP - IP: {0}  country: {1} region： {2}'.format(ip, country, region))
            except:
                logger.error(u'[Error] 接口返回的数据格式不正确')
            else:
                return self._check(country)


def kill_proc():
    """杀掉 firefox/chrome/ie 进程"""
    if CONFIG.browser == 'firefox':
        target = 'firefox'
    elif CONFIG.browser == 'chrome':
        target = 'chrome'
    else:
        target = 'iexplore'
    try:
        logger.info(u'[Info] 清理残留 {} 进程'.format(target))
        os.system('taskkill /F /IM {}.exe'.format(target))
        time.sleep(2)
    except:
        pass


class Browser:
    """浏览器操作类"""
    def __init__(self, proxy):
        self.driver = None
        kill_proc()
        self.error_pages = 0
        self.proxy = proxy

    def pick_a_ua(self):
        with open(UA_FILE, 'rb') as f:
            allf = f.readlines()
            pick = random.choice(allf).strip()
            return pick.split('@')

    def open(self):
        """ 根据config打开指定类型浏览器 """
        if CONFIG.browser == 'firefox':
            try:
                binary = FirefoxBinary(CONFIG.location)
                profile = FirefoxProfile()
                if CONFIG.random_agent:
                    profile.add_extension(os.path.abspath(CONFIG.random_agent))

                platform, ua = self.pick_a_ua()
                logger.info(u'[Info] Platform: {}'.format(platform))
                logger.info(u'[Info] UA: {}'.format(ua))
                profile.set_preference('general.useragent.override', ua)
                profile.set_preference('general.platform.override', platform)

                self.driver = webdriver.Firefox(firefox_binary=binary, firefox_profile=profile)
                logger.info(u'[Info] 打开浏览器  firefox')
                self.driver.set_page_load_timeout(70)
                return self
            except Exception as e:
                logger.error(u'[Error] 打开firefox 浏览器失败')
                raise
        elif CONFIG.browser == 'chrome':
            try:
                option = webdriver.ChromeOptions()
                option.binary_location = CONFIG.location

                platform, ua = self.pick_a_ua()
                logger.info(u'[Info] UA: {}'.format(ua))
                option.add_argument('user-agent={}'.format(ua))

                self.driver = webdriver.Chrome(executable_path='chromedriver.exe', chrome_options=option)
                logger.info(u'[Info] 打开浏览器  chrome')
                self.driver.set_page_load_timeout(70)
                return self
            except:
                logger.error(u'[Error] 打开chrome浏览器失败')
                raise
        elif CONFIG.browser == 'ie':
            try:
                self.driver = webdriver.Ie(executable_path='IEDriverServer.exe')
                logger.info(u'[Info] 打开浏览器  ie')
                self.driver.set_page_load_timeout(70)
                return self
            except:
                logger.error(u'[Error] 打开ie浏览器失败')
        else:
            logger.error(u'[Error] 不支持的浏览器类型')
            os._exit(0)

    def get(self, url):
        """打开URL，成功则返回driver，否则刷新页面，继续尝试，两次失败则重新切一次当前行IP，一共切10次"""
        for i in range(10):
            for j in range(2):
                try:
                    self.driver.get(url)
                    if self.driver.current_url:
                        if self.error_page():
                            if j == 0:  # 第一次error page则刷新，第二次则切代理
                                self.refresh('force')
                                continue
                            else:
                                self.quit()
                                time.sleep(2)
                                self.proxy.call_api()
                                time.sleep(5)
                                self.open()
                                break
                        else:
                            logger.info(u'[Info] 打开URL  {}'.format(url))
                            return self.driver
                    else:
                        raise TimeoutException
                except:
                    logger.error(u'[Error] 打开URL失败')
                    if j != 0:
                        self.quit()
                        time.sleep(2)
                        self.proxy.call_api()
                        time.sleep(5)
                        self.open()
                        break

    def quit(self):
        """清理cookies，关闭浏览器"""
        try:
            self.driver.delete_all_cookies()  # 关闭浏览器之前，清理cookies
            self.driver.quit()
            logger.info(u'[Info] 关闭浏览器')
        except:
            pass

    def refresh(self, force='normal'):
        try:
            logger.info(u'[Info] 刷新页面')
            if force == 'force':
                js = 'location.reload(true)'
                self.driver.execute_script(js)
            else:
                self.driver.refresh()
            time.sleep(10)
        except:
            pass

    def error_page(self):
        # 如果是Error Page，刷新一次，若仍失败，退出
        try:
            if Config.browser == 'firefox':
                WebDriverWait(self.driver, 3, 0.5).until(visibility_of_element_located(('id', 'errorPageContainer')))
            elif Config.browser == 'chrome':
                WebDriverWait(self.driver, 3, 0.5).until(visibility_of_element_located(('id', 'main-frame-error')))
            else:
                WebDriverWait(self.driver, 3, 0.5).until(visibility_of_element_located(('id', 'contentContainer')))
            logger.error(u'[Error] 得到Error Page')
            return True
        except TimeoutException:
            return False


class Element:
    """元素处理类"""
    def __init__(self, driver, elem_info, params):
        self.driver = driver
        try:
            self.locator = (elem_info[0], elem_info[1])
            self.element = WebDriverWait(self.driver, 15, 0.5).until(presence_of_element_located(self.locator))
            self.action = elem_info[2].lower()
            self.element_name = elem_info[3]
            self.params = params
            logger.info(u'[Info] 元素已找到  {}'.format(str(elem_info)))
        except TimeoutException:
            logger.info(u'[Error] 未找到元素  {}'.format(str(elem_info)))

    def do_its_work(self):
        if self.element:
            if self.action == 'click':
                self.element.click()
            elif self.action == 'clear':
                self.element.clear()
            elif self.action == 'submit':
                time.sleep(CONFIG.delay_submit)
                self.element.submit()
            elif self.action == 'sendkeys':
                self.element.send_keys(self.pick_value())
            elif self.action == 'select':
                if self.element_name == 'random':
                    nums = len(Select(self.element).options)
                    logger.info(u'[Info] 随机从网页选择')
                    Select(self.element).select_by_index(random.choice(range(1, nums)))
                elif isinstance(self.element_name, list):
                    logger.info(u'[Info] 从指定选项中随机选择： {}'.format(str(self.element_name)))
                    Select(self.element).select_by_value(random.choice(self.element_name))
                else:
                    Select(self.element).select_by_value(self.pick_value())
            elif self.action == 'readonly_input':  # 去掉readonly，然后sendkeys
                js = "$('input[{0}={1}]').attr('readonly',false)".format(*self.locator)
                self.driver.execute_script(js)
                self.element.send_keys(self.pick_value())
            else:
                logger.error(u"[Error] 不支持的action {}".format(self.action))

    def pick_value(self):
        value = self.params[self.element_name]
        logger.info(u'[Info] 从Excel中取得值 {}'.format(value))
        return value


class Page:
    def __init__(self, driver, elements, params):
        self.driver = driver
        self.elements = elements
        self.params = params
        self.url = self.driver.current_url
        self.error_pages = 0

    def refresh(self, force='normal'):
        logger.info(u'[Info] 刷新页面')
        if force == 'force':
            js = 'location.reload(true)'
            self.driver.execute_script(js)
        else:
            self.driver.refresh()
        time.sleep(10)

    def error_page(self):
        # 如果是Error Page，刷新一次，若仍失败，退出
        for i in range(1, 3):
            try:
                if Config.browser == 'firefox':
                    WebDriverWait(self.driver, 3, 0.5).until(visibility_of_element_located(('id', 'errorPageContainer')))
                elif Config.browser == 'chrome':
                    WebDriverWait(self.driver, 3, 0.5).until(visibility_of_element_located(('id', 'main-frame-error')))
                else:
                    WebDriverWait(self.driver, 3, 0.5).until(visibility_of_element_located(('id', 'contentContainer')))
                self.error_pages = i
                logger.error(u'[Error] 得到Error Page')
                if self.error_pages < 2:
                    time.sleep(3)
                    self.refresh('force')
            except TimeoutException:
                return False
        if self.error_pages == 2:
            logger.error(u'[Error] 两次得到Error Page，任务失败')
            return True

    def do(self):
        skip = False
        for element in self.elements:
            if isinstance(element, dict):  # 特殊命令
                if 'if' in element:
                    skip = False
                    current_handle = self.driver.current_window_handle
                    time.sleep(CONFIG.wait_before_if)
                    WebDriverWait(self.driver, 30, 0.5).until(presence_of_element_located(('tag name', 'html')))
                    found_if = False
                    for handle in self.driver.window_handles:
                        self.driver.switch_to.window(handle)
                        logger.info(u'[Info] 获得URL： {}'.format(self.driver.current_url))
                        if isinstance(element['if'], list):
                            for u in element['if']:
                                if u in self.driver.current_url:
                                    found_if = True
                                    break
                        elif isinstance(element['if'], basestring):
                            if element['if'] in self.driver.current_url:
                                found_if = True
                        else:
                            logger.error(u'[Error] if标签的值必须是list或者str')

                        if found_if:
                            logger.info(u'[Info] 发现匹配URL')
                            if 'action' in element:
                                if element['action'] == 'close':
                                    logger.info(u'[Info] 关闭浏览器')
                                    return True
                                elif element['action'] == 'go':
                                    logger.info(u'[Info] 继续执行')
                                elif element['action'] == 'skip':
                                    skip = True
                                else:
                                    logger.error(u'[Error] 未知动作')
                    if not found_if:
                        logger.info(u'[Info] 未发现匹配网址')
                        if 'else' in element:
                            if element['else'] == 'go':
                                logger.info(u'[Info] 继续执行')
                                self.driver.switch_to.window(current_handle)
                            elif element['else'] == 'close':
                                logger.info(u'[Info] 关闭浏览器')
                                return True
                            elif element['else'] == 'skip':
                                skip = True
                            else:
                                logger.error(u'[Error] 未知动作')
                        elif 'action' in element:
                            if element['action'] == 'close':
                                logger.info(u'[Info] 继续执行')
                                self.driver.switch_to.window(current_handle)
                            else:
                                logger.info(u'[Info] 关闭浏览器')
                                return True

                elif 'wait' in element:
                    if isinstance(element['wait'], list):
                        wait_time = random.randrange(*tuple(element['wait']))
                    else:
                        wait_time = element['wait']
                    logger.info(u'[Info] wait {}s'.format(wait_time))
                    time.sleep(wait_time)
                elif 'refresh' in element:
                    self.refresh(element['refresh'])
                elif 'switch' in element:
                    if element['switch'] == 'default_content':
                        self.driver.switch_to.default_content()
                    else:
                        self.driver.switch_to.frame(element['switch'])
            else:  # 标准元素
                if not skip:
                    try:
                        Element(self.driver, element, self.params).do_its_work()
                    except:
                        logger.warning(u'[Warning] 元素执行失败，跳过该元素')
                    time.sleep(1)


class NoMoreTaskException(Exception):
    pass


class Task:
    def __init__(self, task, proxy):
        self.task = copy.copy(task)
        self.url = self.task.pop(0)['url']
        self.sheet = self.task.pop(0)['sheet']
        self.log = os.path.abspath(os.curdir) + '\\' + self.sheet + '.log'
        self.ran_nums = 0
        self._ran_nums()

        self.proxy = proxy

        taskdata = ExcelReader(sheet=self.sheet)
        self.nums = taskdata.nums
        self.data = taskdata.data

        self.first_page = True

    def _ran_nums(self):
        if os.path.exists(self.log):
            with open(self.log, 'rb') as f:
                self.ran_nums = len(f.read())
        else:
            self.ran_nums = 0
        logger.info(u'[Info] 检测到已执行 {} 次该任务'.format(self.ran_nums))

    def _log(self):
        with open(self.log, 'a') as f:
            f.write('1')
            self.first_page = False

    def _begin(self):
        logger.info(u'[Info] Sheet: "{0}"  Line: "{1}" 开始执行'.format(self.sheet, self.ran_nums + 2))
        logger.info(u'[Info] ======  任务开始  =======')

        self.browser = Browser(self.proxy)
        self.driver = self.browser.open().get(self.url)
        params = self.data[self.ran_nums]
        return params

    def _end(self):
        try:
            logger.info(u'[Info] 当前网页URL： {}'.format(self.driver.current_url))
            self.browser.quit()
        except:
            pass
        logger.info(u'[Info] ======  任务结束  =======')
        logger.info(u'[Info] Sheet: "{0}"  Line: "{1}" 执行结束\n'.format(self.sheet, self.ran_nums + 2))

    def run(self, proxy_log):
        logger.info(u'[Info] 执行任务  {}'.format(self.sheet))
        if self.ran_nums < self.nums:
            params = self._begin()  # begin task and pick params

            for elements in self.task:
                p = Page(self.driver, elements['elements'], params)
                if p.error_page():
                    break
                else:
                    success = p.do()

                # 程序执行完第一个elements，则标记为已执行，写入日志
                if self.first_page:
                    self._log()
                    if proxy_log == 0:
                        logger.info(u'[Info] 执行完第一个elements，写入代理日志')
                        Proxy().log()  # 执行完所有task中的第一个elements，算这个代理已使用过
                        proxy_log = 1
                if success:
                    break
                time.sleep(5)

            self._end()  # end task
        else:
            logger.warning(u'[Warning] data中没有更多的数据了')
            raise NoMoreTaskException()


def main():
    # 循环执行大任务（配置中所有任务节）
    while True:
        finished = False  # 程序结束标记
        if TASKS and CONFIG:
            try:
                p = Proxy()
                p.change()
            except ProxyToolConfigException:
                break

            p.check_ip()

            proxy_log = 0  # 记代理日志的标记，当执行完所有task中第一个page后写入proxy_log
            for task in TASKS:
                try:
                    t = Task(task, p)
                except:
                    logger.error(u'[Error] 初始化任务出错，请检查配置或数据文件，确认填写无误并且变量名与列名对应')
                else:
                    try:
                        proxy_log = t.run(proxy_log)
                    except NoMoreTaskException:
                        finished = True
                        break
                    except Exception as e:
                        logger.error(u'[Error] 执行任务出错，请检查配置与页面是否对应')
                        # logger.exception(e)
                        try:
                            logger.info(u'[Info] 当前网页URL： {}'.format(t.browser.driver.current_url))
                            t.browser.quit()
                        except:
                            pass  # 尝试获取当前URL，关闭浏览器；如果浏览器已被关闭，则pass掉异常
        if finished:
            logger.info(u'[Info] 所有任务执行结束，请处理数据后重新启动程序\n')
            break


if __name__ == '__main__':
    main()
