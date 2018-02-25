import requests
import damatu
import urllib.request
import re
import datetime
import personalInfo
import threading
import time

# 全局request请求
req = requests.Session()
# 获取订票信息
startdate = personalInfo.startDate
backdate = personalInfo.backDate
city = {}
fromStation = personalInfo.fromStation
toStation = personalInfo.toStation
sitType = personalInfo.sitType

# 是否抢票成功
isSuccess = False


def catchPicture():
    picUrl = 'https://kyfw.12306.cn/passport/captcha/captcha-image?login_site=E&module=' \
             'login&rand=sjrand&0.09375183673231757'
    response = req.get(picUrl)
    # response.content是response的内容
    # 它是一个二进制的数据
    # 可以使视频
    # 图片
    # 或者网页源代码
    with open('captcha.jpg', 'wb') as f:
        f.write(response.content)


# 登录模块
# requests发的请求
# 每次都会认为是不同的浏览器
# 但是我们获取了图片之后
# 要用同一个浏览器验证
# requests不能维护同一个cookie
def login():
    # save pictures of verify
    catchPicture()
    dmt = damatu.dmt
    coordinate = ','.join(dmt.decode('captcha.jpg', '287').split('|'))
    data = {
        'answer': coordinate,
        'login_site': 'E',
        'rand': 'sjrand',
        '_json_att': '',
    }
    response = req.post(url='https://kyfw.12306.cn/passport/captcha/captcha-check', data=data)
    if response.json()['result_code'] == '4':
        data = {
            'username': '1171785481@qq.com',
            'password': 'lunhuizhijie123',
            'appid': 'otn',
            '_json_att': '',
        }
        req.post(url='https://kyfw.12306.cn/passport/web/login', data=data)
        data = {
            'appid': 'otn',
            '_json_att': '',
        }
        response2 = req.post(
            url='https://kyfw.12306.cn/passport/web/auth/uamtk',
            data=data)
        print(response2.text)
        newapptk = response2.json()['newapptk']
        response3 = req.post(url='https://kyfw.12306.cn/otn/uamauthclient', data={'tk': newapptk})
        print(response3.text)
    else:
        print('验证失败，正在重新登陆')
        print(response.text)
        login()


def getStations():
    f = open('city.txt', 'rb')
    x = f.readlines()
    f.close()
    for i in range(len(x)):
        x[i] = x[i].decode('utf-8').strip()
        city[x[i].split(' ')[0]] = x[i].split(' ')[1]
    # print(city)


def checkTickets():
    sit_dict = {'软卧': 23, '软座': 24, '硬卧': 28, '硬座': 29}
    # url = 'https://kyfw.12306.cn/otn/leftTicket/queryZ?leftTicketDTO.train_date=2018-01-31&leftTicketDTO.from_station=BJP&leftTicketDTO.to_station=SHH&purpose_codes=ADULT'
    getStations()
    url = 'https://kyfw.12306.cn/otn/leftTicket/queryZ?' \
          'leftTicketDTO.train_date=%s' \
          '&leftTicketDTO.from_station=%s' \
          '&leftTicketDTO.to_station=%s' \
          '&purpose_codes=ADULT' % (startdate, city[fromStation], city[toStation])
    response = requests.get(url).json()
    res = response['data']['result']
    tickets = []
    for x in res:
        arr, index = x.split('|'), sit_dict[sitType]
        if arr[index] == '有' or (arr[index].isdigit() and int(arr[index]) > 0):
            print("查询到匹配车次 %s" % arr[3])
            tickets = arr
    return tickets

    # print(res)


def orderTicket(ticket):
    login()
    response = req.post(url='https://kyfw.12306.cn/otn/login/checkUser', data={'_json_att': ''})
    ticket = checkTickets()
    print('ticket info is')
    print(ticket)
    data = {
        'secretStr': urllib.request.unquote(ticket[0]),  # 转义
        'train_date': startdate,
        'back_train_date': backdate,
        'tour_flag': 'dc',
        'purpose_codes': 'ADULT',
        'query_from_station_name': fromStation,
        'query_to_station_name': toStation,
        'undefined': '',
    }
    res = req.post(url='https://kyfw.12306.cn/otn/leftTicket/submitOrderRequest', data=data)
    if not res.json()['status']:
        print('票票没啦')
        return

    # .* ?就是懒惰模式
    # 可以匹配任何我们要的内容
    # 获取一个订票token
    res = req.post(url='https://kyfw.12306.cn/otn/confirmPassenger/initDc', data={'_json_att': ''})
    # 把页面的global参数找到
    token = re.compile("globalRepeatSubmitToken = '(.*?)';").findall(res.text)  # 获取到的是数组
    # 获取后面要用到的key_is_change参数
    key_is_change = re.compile("'key_check_isChange':'(.*?)'").findall(res.text)  # 获取到的是数组
    if not token:
        print('获取token失败')
        return
    if not key_is_change:
        print('获取key失败')
        return
    token = token[0]
    key_is_change = key_is_change[0]
    print('token is:', token)
    print('key_is_change is:', key_is_change)
    # 下一个请求
    res = req.post(url='https://kyfw.12306.cn/otn/confirmPassenger/getPassengerDTOs',
                   data={'_json_att': '', 'REPEAT_SUBMIT_TOKEN': token})
    print(res.text)
    # 获取手机，姓名，身份证号
    try:
        res = res.json()['data']['normal_passengers'][0]
    except Exception as e:
        print('订票失败，获取不到相应的乘客信息')
        return
    print('开始获取乘客信息')
    try:
        phone, name, id = res.get('mobile_no', ''), res.get('passenger_name', ''), res.get('passenger_id_no', '')
    except Exception as e:
        print('订票失败，获取不到相应的乘客信息：手机， 身份证号和电话')
        return
    print('下单第一步成功')
    data = {
        'cancel_flag': '2',
        'bed_level_order_num': '000000000000000000000000000000',
        'passengerTicketStr': '%s,0,1,%s,1,%s,%s,N' % (seat_type_dict[sitType], name, id, phone),
        'oldPassengerStr': '%s,1,%s,1_' % (name, id),
        'tour_flag': 'dc',
        'randCode': '',
        'whatsSelect': '1',
        '_json_att': '',
        'REPEAT_SUBMIT_TOKEN': token,
    }
    res = req.post(url='https://kyfw.12306.cn/otn/confirmPassenger/checkOrderInfo', data=data)
    print('start checkOrderInfo')
    try:
        res = res.json()
        if not res['status']:
            print('订票失败，status != 200')
            return
    except Exception as e:
        print('订票失败', e)
        return
    print('下单第二步成功')

    data = {
        'train_date': getChinaGoodTime(startdate),
        'train_no': ticket[2],
        'stationTrainCode': ticket[3],
        'seatType': seat_type_dict[sitType],
        'fromStationTelecode': ticket[6],
        'toStationTelecode': ticket[7],
        'leftTicket': ticket[12],
        'purpose_codes': '00',
        'train_location': ticket[15],
        '_json_att': '',
        'REPEAT_SUBMIT_TOKEN': token
    }
    res = req.post(url='https://kyfw.12306.cn/otn/confirmPassenger/getQueueCount', data=data)
    print(res.text)
    try:
        res = res.json()
        if not res['status']:
            print('订票失败')
            return
    except Exception as e:
        print('订票失败')
        return
    print('下单第三步成功')

    print('==================================================')
    data = {
        'passengerTicketStr': '%s,0,1,%s,1,%s,%s,N' % (seat_type_dict[sitType], name, id, phone),
        'oldPassengerStr': '%s,1,%s,1_' % (name, id),
        'randCode': '',
        'purpose_codes': '00',
        'key_check_isChange': key_is_change,
        'leftTicketStr': ticket[12],
        'train_location': ticket[15],
        'choose_seats': '',
        'seatDetailType': '000',
        'whatsSelect': '1',
        'roomType': '00',
        'dwAll': 'N',
        '_json_att': '',
        'REPEAT_SUBMIT_TOKEN': token
    }
    res = req.post(url='https://kyfw.12306.cn/otn/confirmPassenger/confirmSingleForQueue', data=data)
    isSuccess = True
    print(res.text)
    print('抢票成功！！！！！！！！！！！！！！！欢呼声！！！！！！！！！！！尖叫声！！！！！！！！！！！！')


# for test

def getChinaGoodTime(dateStr):  # 获取中国标准时间
    weekday = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    month_array = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    year, month, day = tuple(dateStr.split('-'))
    # print(year,month,day)
    t = datetime.datetime(int(year), int(month), int(day))
    return weekday[t.weekday()] + ' ' + month_array[int(month)] + ' ' + day + ' ' + year + ' 00:00:00 GMT+0800 (中国标准时间)'


def loopGrabTickets():
    try:
        tickets = checkTickets()
        while len(tickets) == 0:
            tickets = checkTickets()
            print("没有票了")
            time.sleep(5)
        print("查票成功")
        print(tickets)
    except Exception as e:
        print(e.__context__)


if __name__ == "__main__":
    t = threading.Thread(target=loopGrabTickets)
    t.start()
# station_names.split('|')
