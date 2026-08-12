from common_lib_mw import kv_com

ip_add = "172.21.0.15"

res = kv_com.read_device_u(ip_add,"DM100")
print(res)