""" KEYENCE KV-5000に対する通信処理
    主に上位リンク通信の処理をラップしたもの。
    FTP通信によるファイルダウンロード処理も含む。
"""

import os
import socket
from ftplib import FTP
from ping3 import ping 
from datetime import datetime, date, timedelta
import re

# Definition of Const ------------------------------------------------------
PORT_NO = 8501      # PLCのポート番号(基本固定されている)
TIMEOUT_SEC = 0.5
USER = 'KV'         # FTPログイン用
PASSWORD = ''       # FTPログイン用

# Definition of Function ------------------------------------------------------
def com_with_plc(ip_add: str, cmd: str) -> str:
    """ KEYENCE KV-5000 上位リンク通信 """
    server = (ip_add, PORT_NO)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as skt:
        skt.settimeout(TIMEOUT_SEC)
        skt.connect(server)
        skt.sendall(cmd.encode("ascii"))
        
        recv_data = b"" # 空bytes
        while True:
            data = skt.recv(4096)

            # 接続が切断された場合(b""が返ってきた場合)
            if not data:
                raise ConnectionError(
                    "PLCとの接続が切断されました"
                )     

            recv_data += data

            # 終端判定
            if recv_data.endswith(b"\r\n"):
                break

        res = recv_data.decode("shift-jis", errors="replace")

        return res.replace("\r\n", "")
    

def read_device_u(ip_add:str, device:str)->str:
    """ PLCのデバイス1点のデータ読み込み
        (データ形式はU:10進数16ビット符号なし)

    Args:
        ip_add (str): PLCのIPアドレス
        device (str): デバイス名

    Returns:
        str: デバイス値またはエラーコード
    """
    cmd = 'RD ' + device +'.U\r'
    return com_with_plc(ip_add, cmd)


def add_device_number(device: str, offset: int) -> str:
    """PLCデバイス番号に指定値を加算する(正規表現に注意)"""

    match = re.fullmatch(r"([A-Za-z]+)(\d+)", device)
    if match is None:
        raise ValueError(f"デバイス名が不正です: {device}")
    
    device_name = match.group(1)
    device_number = int(match.group(2))

    return f"{device_name}{device_number + offset}"


def read_devices_u(ip_add: str, device: str, dev_number: int) -> list[int]:
    """PLCのデバイス連続データ読み込み
    データ形式は U:10進数16ビット符号なし
    最大5000個まで対応
    """
    return _read_devices(ip_add, device, dev_number, "U")


def write_device_u(ip_add:str, device:str, value:int)->str:
    """ PLCのデバイス1点のデータ書き込み
        (データ形式はU:10進数16ビット符号なし)

    Args:
        ip_add (str): PLCのIPアドレス
        device (str): デバイス名
        value (int): 書き込む値

    Returns:
        str: OK(成功時)またはエラーコード
    """
    cmd = 'WR ' + device +'.U ' + str(value) + '\r'
    return com_with_plc(ip_add, cmd)


def write_devices_u(ip_add: str, device: str, values: list[int]) -> str:
    """
    PLCの連続デバイスへ16bit符号なし整数を書き込む。

    Args:
        ip_add: PLCのIPアドレス
        device: 書込み開始デバイス
        values: 書き込む値のリスト

    Returns:
        str: PLCからの応答。正常時は"OK"
    """
    device_count = len(values)

    if not 1 <= device_count <= 1000:
        raise ValueError(
            "書き込みデバイスは1～1000点で指定してください。"
        )
    
    value_text = " ".join(str(value) for value in values)

    command = f"WRS {device}.U {device_count} {value_text}\r"

    response = com_with_plc(ip_add, command)

    if response in ("E1", "E2"):
        raise RuntimeError(f"PLC通信エラー: {response}")
    
    if response != "OK":
        raise RuntimeError(f"PLCから予期しない応答が返されました: {response}")
    
    return response


def read_device_d(ip_add:str, device:str)->str:
    """ PLCのデバイス1点のデータ読み込み
        (データ形式はU:10進数32ビット符号なし)

    Args:
        ip_add (str): PLCのIPアドレス
        device (str): デバイス名

    Returns:
        str: デバイス値またはエラーコード
    """
    cmd = 'RD ' + device +'.D\r'
    return com_with_plc(ip_add, cmd)


def read_devices_d(ip_add: str, device: str, dev_number: int) -> list[int]:
    """PLCのデバイス連続データ読み込み
    データ形式は D:10進数32ビット符号なし
    最大5000個まで対応
    """
    return _read_devices(ip_add, device, dev_number, "D")


def write_device_d(ip_add:str, device:str, value:int)->str:
    """ PLCのデバイス1点のデータ書き込み
        (データ形式はU:10進数32ビット符号なし)

    Args:
        ip_add (str): PLCのIPアドレス
        device (str): デバイス名
        value (int): 書き込む値

    Returns:
        str: OK(成功時)またはエラーコード
    """
    cmd = 'WR ' + device +'.D ' + str(value) + '\r'
    return com_with_plc(ip_add, cmd)


def connect_check(ip_add:str)->bool:
    """PINGを使用した疎通確認を実施
        PLC以外の機器でも使用可能
        LANで使用するためtimeoutは0.2sec

    Args:
        ip_add (str): 接続先IPアドレス

    Returns:
        bool: 応答ありでTrue
    """
    # <不具合修正 2025/10/06>
    # resが0.0(float)で返ってくることがあり、「res==False」が成立する場合があった
    # (Falseは内部的には0として扱われるため)
    res = ping(ip_add, timeout=0.2)
    if res==False and type(res)==bool:
        print(f'{ip_add} : ping=False(error)')  # ForDebug
        return False    # 応答なし(ping エラー発生時)
    elif res==None:
        print(f'{ip_add} : ping=None(timeout)')  # ForDebug
        return False    # 応答なし(pingタイムアウト)
    else:
        return True     # 応答あり


def get_plc_datetime(ip_add:str)->str:
    """ PLC内部の現在年月日時刻を取得(CM700-CM705取得)
        (フォーマット：YYYY/mm/dd hh:MM:ss)

    Args:
        ip_add (str): PLCのIPアドレス
        port_no (int): PLCポート番号(通常8501)

    Returns:
        str: PLC 年月日 時分秒
    """
    dic = {
        'year': ['CM700.U', 0],
        'month': ['CM701.U', 0],
        'day': ['CM702.U', 0],
        'hour': ['CM703.U', 0],
        'minute': ['CM704.U', 0],
        'second': ['CM705.U', 0]
    }
    
    for value in dic.values():
        cmd = 'RD ' + value[0] + '\r'
        value[1] = com_with_plc(ip_add, cmd)[-2:]   #　最終2文字抽出

    val = f"20{dic['year'][1]}/{dic['month'][1]}/{dic['day'][1]} "
    val = val + f"{dic['hour'][1]}:{dic['minute'][1]}:{dic['second'][1]}"
    return val

def set_plc_datetime(ip_add:str)->str:
    """_summary_

    Args:
        ip_add (str): _description_
        port_no (int): _description_

    Returns:
        str: _description_
    """
    now = datetime.now()
    year = str(now.year - 2000).zfill(2)   # 下2桁
    month = str(now.month).zfill(2)
    day = str(now.day).zfill(2)
    hour = str(now.hour).zfill(2)
    minute = str(now.minute).zfill(2)
    second = str(now.second).zfill(2)
    weekday = str(now.weekday()) # 月曜=0/日曜=6
    
    # weekdayをKEYENCE形式(日曜=0/土曜=6)へ変換
    if weekday=='6':  # 日曜
        weekday = '0'
    else:           # 日曜以外
        weekday = str(int(weekday) + 1) 
    
    cmd = f"WRT {year} {month} {day} {hour} {minute} {second} {weekday}\r"
    return com_with_plc(ip_add, cmd)


def dl_alarm_comment(ip_add:str)->list:
    """ PLCのアラーム用デバイスのコメントをダウンロードする
        (対象デバイス=LR10.00-LR29.15の320点)

    Args:
        ip_add (str): PLCのIPアドレス

    Returns:
        list: アラームコメントのリスト
    """
    alarm_info=[]
    for i in range(10,30):
        for j in range(16):
            device = 'LR' + str(i) + str(j).zfill(2)
            cmd = 'RDC '+ device +'\r'
            res = com_with_plc(ip_add, cmd)
            res = res.replace('\r\n','')    # CR&LFの除去
            res = res.replace(' ','')       # スペース除去
            if res=='E6':res='NONE'             # コメントなし(E6)置換
            alarm_info.append([device,res]) # デバイス名-コメント
    
    return alarm_info


def ftp_get_filelist(ip_add:str, folder_name:str)->list:
    """ PLCのSDカード内フォルダのCSVファイル名を取得する
        (フォルダはルートフォルダ内の指定フォルダのみ)
    Args:
        ip_add (str): PLCのIPアドレス
        folder_name (str): SDカードルート上フォルダ名

    Returns:
        list: CSVファイル名のリスト(エラー時は空)
    """
    try:
        # FTPサーバ接続
        ftp = FTP(ip_add)
        ftp.encoding = 'shift-jis'  # KV5000の場合に必須
        ftp.set_pasv('true')
        msg = ftp.login(USER,PASSWORD)
        print(f'   {ip_add}:reply from ftp-server=',msg)

        # ファイル一覧取得(SDカードルート中フォルダのCSVファイルのみ対象)
        folder_path = '/MMC/' + folder_name
        ftp.cwd(folder_path)       # カレントディレクトリ移動
        fpath_list = ftp.nlst('.')   # ファイル一覧取得(フルパス)
        fname_list = [os.path.basename(x) for x in fpath_list]
        fname_list = [n for n in fname_list if n.endswith('.CSV') or n.endswith('.csv')] # CSVファイルのみ
        return fname_list
    except:
        print(f'   {ip_add}:FTP-process failure')
        return []


def ftp_get_file(ip_add:str, folder_name:str, file_name:str, save_folder:str)->bool:
    """ PLCのSDカード内のファイルをダウンロードする

    Args:
        ip_add (str): PLCのIPアドレス
        folder_name (str): SDカードの対象フォルダ名
        file_name (str): DL対象のファイル名
        save_path (str): 保存先フォルダのパス

    Returns:
        bool: 成功時=True / 失敗時=False
    """
    try:
        # FTPサーバ接続
        ftp = FTP(ip_add)
        ftp.encoding = 'shift-jis'  # KV5000の場合に必須
        ftp.set_pasv('true')
        msg = ftp.login(USER,PASSWORD)
        print(f'   {ip_add}:reply from ftp-server=',msg)

        # ファイルダウンロード
        folder_path = '/MMC/' + folder_name
        ftp.cwd(folder_path)       # カレントディレクトリ移動
        f = open(save_folder+'\\'+file_name,'wb')
        ftp.retrbinary('RETR '+file_name, f.write)
        print(f'   {file_name} is downloaded from PLC')
        return True
    except:
        print(f'   {ip_add}:FTP-DL-process failure')
        return False
    

def join_u16_to_u32(upper_value: int, lower_value: int) -> int:
    """2つの16ビット符号なし値を結合して32ビット符号なし値に変換する"""
    if not 0 <= upper_value <= 0xFFFF:
        raise ValueError(f"upper_valueが16ビット範囲外です: {upper_value}")
    
    if not 0 <= lower_value <= 0xFFFF:
        raise ValueError(f"upper_valueが16ビット範囲外です: {lower_value}")

    return (upper_value << 16) | lower_value


def decode_plc_date(date_value: int) -> str:
    """PLCの日付整数(YYMMDD)をYYYY-MM-DD形式の文字列に変換する"""
    year = date_value // 10000
    month = (date_value // 100) % 100
    day = date_value % 100

    # 日付として妥当かチェック
    dt = date(2000 + year, month, day)

    return dt.strftime("%Y-%m-%d")


def kv_seconds_to_datetime_str(seconds: int) -> str:
    """
    キーエンスPLCのSEC命令で取得した秒数を
    YYYY-MM-DD HH:MM:SS形式へ変換する。
    """
    base_datetime = datetime(2000, 1, 1)
    result_datetime = base_datetime + timedelta(seconds=seconds)
    return result_datetime.strftime("%Y-%m-%d %H:%M:%S")


def _read_devices(
        ip_add: str,
        device: str,
        dev_number: int,
        data_type: str
) -> list[int]:
    """PLCのデバイス連続データ読み込み共通処理"""
    max_total_number = 5000

    if not 1 <= dev_number <= max_total_number:
        raise ValueError(
            f"指定されたデバイス数が不正です: {dev_number}"
        )
    
    if data_type == "U":
        max_once_number = 1000
        device_step = 1

    elif data_type == "D":
        max_once_number = 500
        device_step = 2

    else:
        raise ValueError(
            f"対応していないデータ形式です: {data_type}"
        )

    values: list[int] = []
    read_count = 0

    while read_count < dev_number:
        read_number = min(max_once_number, dev_number - read_count)
        device_offset = read_count * device_step
        start_device = add_device_number(device, device_offset)

        cmd = f"RDS {start_device}.{data_type} {read_number}\r"
        res = com_with_plc(ip_add, cmd)

        if res in ("E1", "E2"):
            raise RuntimeError(f"PLC通信エラー: {res}")
        
        try:
            partial_values = [int(x) for x in res.split()]
        except ValueError as e:
            raise RuntimeError(f"PLC応答を数値に変換できません: {res}") from e
        
        if len(partial_values) != read_number:
            raise RuntimeError(
                f"PLC応答数が不正です: 要求={read_number}, "
                f"実際={len(partial_values)}, 応答={res}"
            )
        
        values.extend(partial_values)
        read_count += read_number

    return values






# テストコード(動作確認用) -----------------------------------------------------------------
if __name__=='__main__':

    ip_add = "172.20.1.111"
    ip_add = "192.168.8.1"

    res = write_devices_u(ip_add, "EM10000", [0,0])
    print(res)
    exit()

    res = read_devices_u(ip_add, 'ZF0', 1500)
    print(res)
    print(len(res))

    exit()


    # cmd = 'WR DM1990.U 6000\r'
    res = read_device_u(ip_add, 'DM1990')
    print(res)
    exit()

    if connect_check(ip_add):
        res = ''
        # res = com_with_plc(ip_add, cmd)
        # res = read_device_u(ip_add, 'DM1990')
        # res = write_device_u(ip_add, 'DM1990', 6500)
        # res = set_plc_datetime(ip_add)
        # res = get_plc_datetime(ip_add)
        # res = dl_alarm_comment(ip_add)
        print(res)

        if False:
            plc_folder='operation_data'
            save_folder = os.path.expanduser('~/Desktop')   # デスクトップパス
            flist = ftp_get_filelist(ip_add, plc_folder)
            print(flist)
            ftp_get_file(ip_add,plc_folder,flist[1],save_folder)
        
    else:
        print(f'{ip_add}: Connectivity False')




"""
----- 更新履歴 -----

2026.7.22
    write_devices_u 追加 （PLC一括リセット用)

2026.7.10
    read_devices_d 最大数500→5000へ
    _read_devicesによる共通処理関数化

2026.7.9
以下関数追加
    read_devices_d
    kv_seconds_to_datetime_str

2026.7.8
以下関数追加
    read_device_d
    write_device_d

2026.6.27
以下関数追加
    read_devices_u
    join_u16_to_u32
    decode_plc_date

2026.5.10
ChatGPTのアドバイスにより、com_with_plcをリニューアル。
・分割受信(分割判定)
・途中切断による例外発生
に対応した。


"""
