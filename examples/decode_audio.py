import copy
import os.path

from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES
import base64
import argparse


def encoded_audio_to_sound_file(config, encoded_audio, output_file_path):

    encrypted_bytes = base64.b64decode(encoded_audio)
    key = RSA.importKey(open(config.ssh_file).read(),
                        passphrase=config.ssh_password)
    cipher = PKCS1_OAEP.new(key)

    decrypted_header = cipher.decrypt(
        encrypted_bytes[:key.size_in_bytes()])

    aes_key = decrypted_header[:AES.block_size]
    iv = decrypted_header[AES.block_size:]

    aes_cipher = AES.new(aes_key, AES.MODE_CBC,
                         iv)
    decrypted_audio = aes_cipher.decrypt(
        encrypted_bytes[key.size_in_bytes():])
    format = ".raw"
    if "Ogg" == decrypted_audio[:3].decode():
        format = ".ogg"
    elif "fLaC" == decrypted_audio[:4].decode():
        format = ".flac"
    with open(output_file_path+format, "wb") as out_fp:
        out_fp.write(decrypted_audio)

def main():
    parser = argparse.ArgumentParser(
        description='This program read audio from compressed json produced'
                    ' by zerotrigger.py',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-i", "--input",
                        help="Path of the compressed flac file",
                        required=True, type=str)
    parser.add_argument("--ssh_file",
                        help="private key file for audio decryption",
                        required=True)
    parser.add_argument("--ssh_password",
                        help="password of private key", default=None, type=str)
    parser.add_argument("-o", "--output",
                        help="Path of the output audio file",
                        type=str)
    args = parser.parse_args()

    output = args.output if args.output != None else args.input+"decoded"

    if args.output == None and args.input.endswith(".flac.b64"):
        output = args.input[:-9]
    with open(args.input, "r") as fp:
        encoded_audio = fp.read()
        encoded_audio_to_sound_file(args, encoded_audio, output)


if __name__ == "__main__":
    main()
