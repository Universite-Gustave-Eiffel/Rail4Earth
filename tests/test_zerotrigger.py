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
import unittest
import soundfile as sf
import types

from services.zero_trigger import TriggerProcessor

class TestZeroTrigger(unittest.TestCase):

    def test_trigger(self):
        config = {
            "trigger_count": 400,
            "trigger_ban": ["Speech"],
            "trigger_ban_threshold": [], # use default yamnet
            "configuration_file": "",
            "trigger_tag": ["Train", "Rail transport", "Railroad car, train wagon"],
            "trigger_threshold": [0.07],
            "order_threshold": [8],
            "min_leq": 30.0,
            "total_length": 60.0,
            "cached_length": 30.0,
            "sample_rate": 16000,
            "resample_method": "kaiser_fast",
            "sample_format": "FLOAT_LE",
            "ssh_file": "~/.ssh/id_rsa.pub",
            "input_address": "tcp://127.0.0.1:10001",
            "output_address_recording": "tcp://127.0.0.1:10002",
            "output_address_recognition": "tcp://127.0.0.1:10003",
            "yamnet_class_map": "third_parties/yamnet/yamnet/yamnet_class_threshold_map.csv",
            "yamnet_weights": "third_parties/yamnet/yamnet/yamnet.tflite",
            "yamnet_cutoff_frequency": 0,
            "yamnet_max_gain": 24.0,
            "yamnet_window_time": 5.0,
            "sensitivity": -28.34,
            "delay_print_samples": 300,
            "add_spectrogram": False,
            "verbose": False
        }
        config = types.SimpleNamespace(**config)
        trigger = TriggerProcessor(config)

        data, sr = sf.read('tests/test_trains_with_voice_16kHz_24bit.wav', dtype='float32')

        # Split the audio data into subsets of 5 seconds
        yamnet_audio_length = int(config.yamnet_window_time * sr)  # 5 seconds * sample rate
        yamnet_audio_blocks = [data[i:i+yamnet_audio_length] for i in range(0, len(data), yamnet_audio_length)]

        cache_nb_blocks = config.total_length // config.yamnet_window_time
        yamnet_audio_cache = []

        print(len(yamnet_audio_blocks))

        wait_blocks = 0
        trains = []
        bans = []
        # Process each subset using trigger.generate_yamnet_document
        for i, yamnet_audio in enumerate(yamnet_audio_blocks):

            # Add the audio to the cache
            yamnet_audio_cache.append(yamnet_audio)
            if len(yamnet_audio_cache) > cache_nb_blocks:
                yamnet_audio_cache.pop(0)

            if wait_blocks == 0:
                document = trigger.generate_yamnet_document_tags(yamnet_audio, config.trigger_tag, config.add_spectrogram)
            
                do_trigger = trigger.should_trigger(document)

                if document["scores"]["Rail transport"] >= 0.03:
                    print(document)
                if do_trigger:
                    print("TRAIN !!! at %ds" % (i*5))
                    trains.append(i)
                    wait_blocks = config.cached_length // config.yamnet_window_time
            
            elif wait_blocks > 0:
                wait_blocks -= 1
                if wait_blocks == 0:
                    for yamnet_audio_cache_block in yamnet_audio_cache:
                        ban_document = trigger.generate_yamnet_document_tags(yamnet_audio_cache_block, config.trigger_ban, config.add_spectrogram)
                        if trigger.should_ban(ban_document):
                            print(ban_document)
                            break
            
        self.assertEqual(train_count, 5)

if __name__ == '__main__':
    unittest.main()

