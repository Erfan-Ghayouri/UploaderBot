CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

def encode_base62(number: int) -> str:
    if number == 0:
        return CHARS[0]

    result = ""

    while number:
        number, remainder = divmod(number, 62)
        result = CHARS[remainder] + result

    return result

def decode_base62(value: str) -> int:
    number = 0

    for char in value:
        number = number * 62 + CHARS.index(char)

    return number

a = 123
a_encoded = encode_base62(a)
a_decoded = decode_base62(a_encoded)
if a == a_decoded:
    print(a)
    print(a_encoded)
    print(a_decoded)