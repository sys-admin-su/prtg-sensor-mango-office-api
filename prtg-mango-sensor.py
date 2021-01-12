import requests
import json
import hashlib
import datetime
import time
from sys import exit, argv

api_url = "	https://app.mango-office.ru/vpbx/"
api_key = ""
api_salt = ""
stat_loop_seconds = 10   # 3 times;seconds

# ====================================================================================


def make_request(url, request):
    """
    Pass actual request to API
    """
    payload = {"vpbx_api_key": api_key,
               "sign": get_sign(json.dumps(request)),
               "json": json.dumps(request)}
    try:
        req = requests.post(url, data=payload)
    except Exception as e:
        return_error("Python runtime error. Message: {}".format(e.args[0]))
    else:
        if req.status_code == 200 or req.status_code == 204:
            return {'error': False, 'data': req}
        else:
            return {'error': True, 'data': req}


def get_sign(request):
    """
    Prepare sign string
    """
    try:
        sign = hashlib.sha256((api_key + request + api_salt).encode('utf8'))
    except Exception as e:
        return_error("Python runtime error. Message: {}".format(e.args[0]))
    else:
        return sign.hexdigest()


def get_balance():
    """
    Retrieving account balance
    """
    # global exec_error, exec_error_msg
    api_method = "account/balance"
    request = {}    # empty
    url = api_url + api_method
    answer = make_request(url, request)
    if answer['error']:
        # server answer is not 200
        return_error("HTTP Request error. HTTP Code: {}\nMessage: {}".format(answer['data'].status_code, answer['data'].text))
    else:
        # server answer is 200
        return {'error': False, "data": answer['data'].text}


def get_missed_calls():
    """
    Retrieving missing calls
    """
    api_method = "stats/request"
    url = api_url + api_method
    request = {'date_to': time.mktime(datetime.datetime.now().timetuple()),
               'date_from': time.mktime((datetime.datetime.now() - datetime.timedelta(minutes=missing_calls_interval)).timetuple()),
               'fields': "to_extension, from_number, start, finish, answer, disconnect_reason, from_extension"}
    answer = make_request(url, request)
    if answer['error']:
        # server answer is not 200
        return_error("HTTP Request error. HTTP Code: {}\nMessage: {}".format(answer['data'].status_code, answer['data'].text))
    else:
        # server answer is 200 or 204
        stat_id = json.loads(answer['data'].text)['key']
        api_method = "stats/result"
        url = api_url + api_method
        request = {
            'key': stat_id
        }
        answer = make_request(url, request)
        i = 0
        stat = []
        while not answer['error'] and answer['data'].status_code != 200 or i == 3:
            time.sleep(stat_loop_seconds)
            # print(i)
            answer = make_request(url, request)
            i += 1
        if i == 3:
            return_error("Timeout for requesting statistics (30 seconds). Try lowering time delta")
        elif answer['error']:
            return_error("HTTP Request error. HTTP Code: {}\nMessage: {}".format(answer['data'].status_code,
                                                                                 answer['data'].text))
        else:
            for entry in answer['data'].text.splitlines():
                n = entry.split(";")
                if int(n[4]) == 0 and n[6] == '':
                    n[2] = datetime.datetime.fromtimestamp(int(n[2])).strftime('%Y-%m-%d %H:%M:%S')
                    n[3] = datetime.datetime.fromtimestamp(int(n[3])).strftime('%Y-%m-%d %H:%M:%S')
                    stat.append(n)
            return {'error': False, "data": stat}


def return_error(msg):
    """
    Returns JSON encoded error to PRTG backend
    """
    prtg_dict = {"prtg": {"error": 1, "text": msg}}
    print(json.dumps(prtg_dict))
    exit()


def main():
    prtg_dict = {"prtg": {"result": []}}
    # get balance
    bal = get_balance()
    if not bal['error']:
        prtg_dict["prtg"]["result"].append({"channel": "Баланс",
                                            "value": json.loads(bal['data'])['balance'],
                                            "unit": "Custom",
                                            "customunit": "RUB",
                                            "float": 1,
                                            "limitminerror": 0,
                                            "limitminwarning": 1000,
                                            "limitmode": 1,
                                            })
    # get statistics (missed calls
    mcalls = get_missed_calls()
    if not mcalls['error']:
        prtg_dict["prtg"]["result"].append({"channel": "Пропущенных вызовов".format(missing_calls_interval),
                                            "value": len(mcalls['data']),
                                            "float": 0,
                                            "limitmaxerror": 0,
                                            "limitmaxwarning": missing_calls_interval,
                                            "limitmode": 1,
                                            })
    return prtg_dict


if __name__ == '__main__':
    try:
        if len(argv) == 4:
            api_key = argv[1]
            api_salt = argv[2]
            missing_calls_interval = int(argv[3])
            if missing_calls_interval <= 43200:
                m = main()
                print(json.dumps(m))
            else:
                return_error("Incorrect time delta for missing calls. It can't be more than 30 days (43200 minutes)")
        else:
            return_error("Incorrect arguments. Use ./script api_key api_salt missing_call_delta_minutes")
    except Exception as e:
        return_error("Python runtime error. Message: {}".format(e.args[0]))
