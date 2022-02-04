#! /usr/bin/env python3

import argparse
import atexit
import glob
import os
import signal
import subprocess
import sys
import time
import unittest

from hwilib._cli import process_commands
from test_device import (
    DeviceEmulator,
    DeviceTestCase,
    start_bitcoind,
    TestDeviceConnect,
    TestDisplayAddress,
    TestGetKeypool,
    TestGetDescriptors,
    TestSignMessage,
    TestSignTx,
)

class ColdcardSimulator(DeviceEmulator):
    def __init__(self, simulator):
        try:
            os.unlink("coldcard-emulator.stdout")
        except FileNotFoundError:
            pass
        self.simulator = simulator
        self.coldcard_log = None
        self.coldcard_proc = None

    def start(self):
        self.coldcard_log = open("coldcard-emulator.stdout", "a")
        # Start the Coldcard simulator
        self.coldcard_proc = subprocess.Popen(
            [
                "python3",
                os.path.basename(self.simulator), "--ms"
            ],
            cwd=os.path.dirname(self.simulator),
            stdout=self.coldcard_log,
            preexec_fn=os.setsid
        )
        # Wait for simulator to be up
        while True:
            try:
                enum_res = process_commands(["enumerate"])
                found = False
                for dev in enum_res:
                    if dev["type"] == "coldcard" and "error" not in dev:
                        found = True
                        break
                if found:
                    break
            except Exception:
                pass
            time.sleep(0.5)
        atexit.register(self.stop)

    def stop(self):
        if self.coldcard_proc.poll() is None:
            os.killpg(os.getpgid(self.coldcard_proc.pid), signal.SIGTERM)
            os.waitpid(os.getpgid(self.coldcard_proc.pid), 0)
        self.coldcard_log.close()
        atexit.unregister(self.stop)

# Coldcard specific management command tests
class TestColdcardManCommands(DeviceTestCase):
    def test_setup(self):
        result = self.do_command(self.dev_args + ['-i', 'setup'])
        self.assertIn('error', result)
        self.assertIn('code', result)
        self.assertEqual(result['error'], 'The Coldcard does not support software setup')
        self.assertEqual(result['code'], -9)

    def test_wipe(self):
        result = self.do_command(self.dev_args + ['wipe'])
        self.assertIn('error', result)
        self.assertIn('code', result)
        self.assertEqual(result['error'], 'The Coldcard does not support wiping via software')
        self.assertEqual(result['code'], -9)

    def test_restore(self):
        result = self.do_command(self.dev_args + ['-i', 'restore'])
        self.assertIn('error', result)
        self.assertIn('code', result)
        self.assertEqual(result['error'], 'The Coldcard does not support restoring via software')
        self.assertEqual(result['code'], -9)

    def test_backup(self):
        result = self.do_command(self.dev_args + ['backup'])
        self.assertTrue(result['success'])
        for filename in glob.glob("backup-*.7z"):
            os.remove(filename)

    def test_pin(self):
        result = self.do_command(self.dev_args + ['promptpin'])
        self.assertIn('error', result)
        self.assertIn('code', result)
        self.assertEqual(result['error'], 'The Coldcard does not need a PIN sent from the host')
        self.assertEqual(result['code'], -9)

        result = self.do_command(self.dev_args + ['sendpin', '1234'])
        self.assertIn('error', result)
        self.assertIn('code', result)
        self.assertEqual(result['error'], 'The Coldcard does not need a PIN sent from the host')
        self.assertEqual(result['code'], -9)

class TestColdcardGetXpub(DeviceTestCase):
    def test_getxpub(self):
        result = self.do_command(self.dev_args + ['--expert', 'getxpub', 'm/44h/0h/0h/3'])
        self.assertEqual(result['xpub'], 'tpubDFHiBJDeNvqPWNJbzzxqDVXmJZoNn2GEtoVcFhMjXipQiorGUmps3e5ieDGbRrBPTFTh9TXEKJCwbAGW9uZnfrVPbMxxbFohuFzfT6VThty')
        self.assertTrue(result['testnet'])
        self.assertFalse(result['private'])
        self.assertEqual(result['depth'], 4)
        self.assertEqual(result['parent_fingerprint'], 'bc123c3e')
        self.assertEqual(result['child_num'], 3)
        self.assertEqual(result['chaincode'], '806b26507824f73bc331494afe122f428ef30dde80b2c1ce025d2d03aff411e7')
        self.assertEqual(result['pubkey'], '0368000bdff5e0b71421c37b8514de8acd4d98ba9908d183d9da56d02ca4fcfd08')

def coldcard_test_suite(simulator, rpc, userpass, interface):
    dev_type = "coldcard"
    sim_path = "/tmp/ckcc-simulator.sock"
    fpr = "0f056943"
    xpub = "tpubDDpWvmUrPZrhSPmUzCMBHffvC3HyMAPnWDSAQNBTnj1iZeJa7BZQEttFiP4DS4GCcXQHezdXhn86Hj6LHX5EDstXPWrMaSneRWM8yUf6NFd"
    signtx_cases = [
        (["legacy"], True, True, False),
        (["segwit"], True, True, False),
        (["legacy", "segwit"], True, True, False),
    ]

    dev_emulator = ColdcardSimulator(simulator)

    # Generic device tests
    suite = unittest.TestSuite()
    suite.addTest(DeviceTestCase.parameterize(TestColdcardManCommands, rpc, userpass, dev_type, dev_type, sim_path, fpr, '', emulator=dev_emulator, interface=interface))
    suite.addTest(DeviceTestCase.parameterize(TestColdcardGetXpub, rpc, userpass, dev_type, dev_type, sim_path, fpr, xpub, emulator=dev_emulator, interface=interface))
    suite.addTest(DeviceTestCase.parameterize(TestDeviceConnect, rpc, userpass, dev_type, dev_type, sim_path, fpr, xpub, emulator=dev_emulator, interface=interface))
    suite.addTest(DeviceTestCase.parameterize(TestDeviceConnect, rpc, userpass, 'coldcard_simulator', dev_type, sim_path, fpr, xpub, emulator=dev_emulator, interface=interface))
    suite.addTest(DeviceTestCase.parameterize(TestGetDescriptors, rpc, userpass, dev_type, dev_type, sim_path, fpr, xpub, emulator=dev_emulator, interface=interface))
    suite.addTest(DeviceTestCase.parameterize(TestGetKeypool, rpc, userpass, dev_type, dev_type, sim_path, fpr, xpub, emulator=dev_emulator, interface=interface))
    suite.addTest(DeviceTestCase.parameterize(TestDisplayAddress, rpc, userpass, dev_type, dev_type, sim_path, fpr, xpub, emulator=dev_emulator, interface=interface))
    suite.addTest(DeviceTestCase.parameterize(TestSignMessage, rpc, userpass, dev_type, dev_type, sim_path, fpr, xpub, emulator=dev_emulator, interface=interface))
    suite.addTest(DeviceTestCase.parameterize(TestSignTx, rpc, userpass, dev_type, dev_type, sim_path, fpr, xpub, emulator=dev_emulator, interface=interface, signtx_cases=signtx_cases))

    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    return result.wasSuccessful()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test Coldcard implementation')
    parser.add_argument('simulator', help='Path to the Coldcard simulator')
    parser.add_argument('bitcoind', help='Path to bitcoind binary')
    parser.add_argument('--interface', help='Which interface to send commands over', choices=['library', 'cli', 'bindist'], default='library')
    args = parser.parse_args()

    # Start bitcoind
    rpc, userpass = start_bitcoind(args.bitcoind)

    sys.exit(not coldcard_test_suite(args.simulator, rpc, userpass, args.interface))
