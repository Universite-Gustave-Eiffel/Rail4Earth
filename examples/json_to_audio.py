import copy
import os.path

from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES
import base64
import json
import gzip
import argparse
import csv
import sys


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


def get_sf(config):
    with gzip.open(config.document_gz, 'rt') as fp:
        document = json.load(fp)
        if "encrypted_audio" in document and len(document["encrypted_audio"]) > 0:
            encoded_audio_to_sound_file(config, document["encrypted_audio"],
                                        config.audio_file)


def sanitize_file_name(s):
    return "".join([c for c in s.replace(":", "_") if c.isalpha() or c.isdigit() or
                    c in (' ', '_')]).rstrip()


def get_sf_from_csv(config, csv_file):
    with open(csv_file, "r") as fp:
        csv.field_size_limit(sys.maxsize)
        reader = csv.reader(fp)
        columns = next(reader)
        date_column = columns.index("date")
        encrypted_audio_column = columns.index("encrypted_audio")
        for data_columns in reader:
            encrypted_audio = data_columns[encrypted_audio_column]
            if len(encrypted_audio) > 16:
                audio_path = os.path.join(os.path.dirname(csv_file), sanitize_file_name(
                    data_columns[date_column]))
                config.audio_file = audio_path
                encoded_audio_to_sound_file(config, encrypted_audio, audio_path)


def main():
    parser = argparse.ArgumentParser(
        description='This program read audio from compressed json produced'
                    ' by zerotrigger.py',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--document_gz",
                        help="Path of the compressed json file",
                        required=True, type=str)
    parser.add_argument("--ssh_file",
                        help="private key file for audio decryption",
                        required=True)
    parser.add_argument("--ssh_password",
                        help="password of private key", default=None, type=str)
    parser.add_argument("--audio_file",
                        help="Path of the output audio file",
                        default="audio", type=str)
    args = parser.parse_args()
    if os.path.isdir(args.document_gz):
        documents = [filepath for filepath in os.listdir(args.document_gz) if
                     filepath.endswith(".json.gz") and filepath.startswith("yamnet_")]
        for document in documents:
            args_cp = copy.copy(args)
            args_cp.document_gz = os.path.join(args.document_gz, document)
            args_cp.audio_file = os.path.join(args.document_gz,
                                              document[:document.rfind(".json.gz")])
            try:
                get_sf(args_cp)
            except KeyError as e:
                print("Cannot read %s" % document)
    else:
        if args.document_gz.endswith(".json.gz"):
            get_sf(args)
        elif args.document_gz.endswith(".csv"):
            # kibana share method
            get_sf_from_csv(args, args.document_gz)


if __name__ == "__main__":
    main()
