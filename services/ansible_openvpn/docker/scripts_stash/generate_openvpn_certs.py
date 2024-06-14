#  BSD 3-Clause License
#
#  Copyright (c) 2023, University Gustave Eiffel
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#   Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#   Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#   Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import subprocess

def main():
    certs_common_name = ["28_7dc7",
    "31_fd10",
    "42_adbd",
    "03_daa9",
    "06_4c98",
    "22_427d",
    "44_7ca3",
    "25_c0d3",
    "13_f680",
    "46_373f",
    "19_27bf",
    "05_df3a",
    "07_874e",
    "16_d0a3",
    "10_d082",
    "20_c7cd",
    "02_e223",
    "12_0b6c",
    "33_83f0",
    "27_9277",
    "32_87b9",
    "35_08e9",
    "34_1113",
    "43_9eb6",
    "26_a960",
    "40_7b9c",
    "15_5987",
    "18_f54f",
    "30_d1e5",
    "01_cc15",
    "14_7cac",
    "17_5c6b",
    "39_88cd",
    "11_e1cd",
    "36_8aa9",
    "23_5557",
    "45_ebea",
    "24_d70d",
    "41_79b3",
    "09_1288",
    "38_821c",
    "21_3f83",
    "37_92e2",
    "08_3d54",
    "29_f627"]

    for client_name in certs_common_name:
        print(subprocess.getoutput("sudo docker compose run --rm openvpn easyrsa build-client-full %s nopass" % client_name))
        print(subprocess.getoutput("sudo docker compose run --rm openvpn ovpn_getclient %s > %s.ovpn" % client_name))


if __name__ == '__main__':
    main()

