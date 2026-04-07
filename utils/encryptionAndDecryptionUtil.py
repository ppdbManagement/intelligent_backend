# 解密token
import base64
import datetime
from urllib import request
import jwt
from Crypto.Cipher import PKCS1_v1_5 as Cipher_pksc1_v1_5
from Crypto.PublicKey import RSA

from control.models import User

private_key_file = "./static/key/pri.key"
public_key_file = "./static/key/pub.key"
# 解密token


def token_decrypt(token):
    salt = '*&&%^%#$$'
    try:
        data = jwt.decode(token, salt, algorithms=[
                          'HS256'], detached_payload=False)
        return data, True
    except jwt.ExpiredSignatureError:
        return {"msg": '登录已过期'}, False
    except jwt.DecodeError:
        return {"msg": '用户信息认证失败'}, False
    except jwt.InvalidTokenError:
        return {"msg": '无效的登录信息'}, False

# 加密token


def token_encryption(user, duration):  # 需要两个参数，用户登录信息和token保存时长（第二个参数表示天数）
    salt = "*&&%^%#$$"
    payload = {
        "user_account": user["user_account"],
        "key": user["key"],
        # exp 配置token有效时长天数
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=duration),
    }
    token = jwt.encode(payload=payload, key=salt, algorithm="HS256")
    return token

# RSA解密


def rsa_decrypt(encrypt_msg):
    with open(private_key_file, "r", encoding="utf-8") as f:
        pri = f.read()  # 解密私钥
        private_key = "-----BEGIN PRIVATE KEY-----\n" + \
                      pri + "\n-----END PRIVATE KEY-----"
        decodeStr = base64.b64decode(encrypt_msg)
        rsa_key = RSA.importKey(private_key)
        pri_key = Cipher_pksc1_v1_5.new(rsa_key)
        encry_text = pri_key.decrypt(decodeStr, b"rsa")
        return encry_text.decode("utf8")

# 从token中获取用户信息


def get_useraccount_from_request(request):
    token = request.META.get('HTTP_TOKEN', None)
    data, status = token_decrypt(token)
    if status:
        return data["user_account"]
    else:
        return None

# 从user_account 获取


def get_user_from_useraccount(user_account):
    if user_account is None:
        return None
    return User.objects.filter(user_account=user_account).first()

# 密码加密


def encryptor_psd(password: str) -> str:
    # 公钥
    key = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAml4xtv7nCX60taROCzaZ
GeY7AUhvMSg55ZTnv167csMy9QSFATByLbGnHaRejtQnOKUq9Ri94X5jHYCFCqYy
ImpUydpv1PWimUKFaVmDxK2xIAX1UTwpIT8C2LdM98RPvD3z4soH0n2tYJkR8Q9G
Gtw89jTyVkUQRnZr/RBgosOwYcpQnh5k1X0ObpyqowdamLf7nKxmndk9krw1f5zJ
YOqhlBVijqxylxOmlR0HHQKtrEgcB66uSMblI4Zc4fxQlPUXiOIAGIvLT95Kl2M1
k9rvMUePo18gKbr1N0wHYV2UKo7Kj9ZOJ0Ae1AfIVYPbrrLLLlV0JWlr+YgDPnij
WwIDAQAB
-----END PUBLIC KEY-----"""

    # 加载公钥
    rsa_key = RSA.import_key(key)
    cipher = Cipher_pksc1_v1_5.new(rsa_key)

    # 加密
    encrypted_password = cipher.encrypt(password.encode('utf-8'))

    # 返回 base64 编码的加密结果
    return base64.b64encode(encrypted_password).decode('utf-8')
