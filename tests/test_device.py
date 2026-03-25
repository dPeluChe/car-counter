"""Tests para carcounter/device.py"""

from carcounter.device import detect_device


class TestDetectDevice:
    def test_explicit_cpu(self):
        device, desc = detect_device("cpu")
        assert device == "cpu"
        assert desc == "cpu"

    def test_explicit_cuda(self):
        device, desc = detect_device("cuda")
        assert device == "cuda"
        assert desc == "cuda"

    def test_explicit_mps(self):
        device, desc = detect_device("mps")
        assert device == "mps"
        assert desc == "mps"

    def test_auto_returns_valid(self):
        device, desc = detect_device("auto")
        assert device in ("cpu", "cuda", "mps")
        assert len(desc) > 0
