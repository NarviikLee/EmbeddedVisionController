"""Hardware-free checks; run from the repository root."""
import contextlib
import io
import runpy
import unittest
from unittest.mock import Mock, patch

import numpy as np

from scripts.test_input import find_target
from communication.serial_comm import send_track, receive_packet
from vision.detector import determine_direction


class TrackingTests(unittest.TestCase):
    def test_target_selection(self):
        car = {"label": "car"}
        first = {"label": "person", "direction": "LEFT"}
        second = {"label": "person", "direction": "RIGHT"}
        self.assertIs(find_target([car, first, second]), first)
        self.assertIs(find_target([car, first], "car"), car)
        self.assertIsNone(find_target([]))
        self.assertIsNone(find_target([car]))

    def test_direction_boundaries(self):
        for center, expected in ((259, "LEFT"), (260, "CENTER"),
                                 (380, "CENTER"), (381, "RIGHT")):
            with self.subTest(center=center):
                self.assertEqual(determine_direction(center, 640), expected)

    def test_track_packet_and_response(self):
        port = Mock()
        for direction in ("LEFT", "CENTER", "RIGHT"):
            packet = f"TRACK:{direction}\n".encode()
            port.write.return_value = len(packet)
            self.assertEqual(send_track(port, direction), len(packet))
            port.write.assert_called_with(packet)
        port.readline.return_value = b"ACK:LEFT\n"
        self.assertEqual(receive_packet(port), ("ACK", "LEFT"))
        port.readline.return_value = b""
        with self.assertRaises(TimeoutError):
            receive_packet(port)
        port.readline.return_value = b"INVALID\n"
        with self.assertRaises(ValueError):
            receive_packet(port)

    def run_camera_loop(self, options, interrupted=False):
        camera, port = Mock(), Mock()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        camera.isOpened.return_value = True
        directions = ("LEFT", "LEFT", None, "LEFT", "RIGHT")
        reads = [(True, frame)] * len(directions)
        reads.append(KeyboardInterrupt() if interrupted else (False, None))
        camera.read.side_effect = reads
        results = [([], [] if d is None else [{"label": "person", "direction": d}])
                   for d in directions]
        with contextlib.ExitStack() as stack:
            def mocked(name, **kwargs):
                return stack.enter_context(patch(name, **kwargs))
            mocked("sys.argv", new=["scripts.test_input", *options])
            mocked("vision.detector.load_model", return_value=(Mock(), [{"shape": [1, 320, 320, 3]}], []))
            mocked("vision.detector.load_label", return_value=["person"])
            mocked("vision.detector.preprocess_frame", return_value=frame)
            mocked("vision.detector.run_inference", return_value=(None,) * 4)
            mocked("vision.detector.postprocess_detections", side_effect=results)
            mocked("cv2.VideoCapture", return_value=camera)
            show = mocked("cv2.imshow")
            mocked("cv2.waitKey", return_value=-1)
            destroy = mocked("cv2.destroyAllWindows")
            mocked("communication.serial_comm.connect_serial", return_value=port)
            # Use real packet generation/parsing through the mocked serial port.
            port.write.return_value = 11
            port.readline.return_value = b"ACK:OK\n"
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                runpy.run_path("scripts/test_input.py", run_name="__main__")
        self.assertEqual([c.args[0] for c in port.write.call_args_list],
                         [b"TRACK:LEFT\n", b"TRACK:RIGHT\n"])
        self.assertEqual(port.readline.call_count, 2)
        camera.release.assert_called_once()
        port.close.assert_called_once()
        return show, destroy, output.getvalue()

    def test_headless_verbose_and_interrupt(self):
        show, destroy, output = self.run_camera_loop(["--headless", "--verbose"], interrupted=True)
        show.assert_not_called()
        destroy.assert_not_called()
        self.assertIn("'label': 'person'", output)
        self.assertIn("Stopped by user", output)

    def test_default_gui_without_verbose(self):
        show, destroy, output = self.run_camera_loop([])
        self.assertEqual(show.call_count, 5)
        destroy.assert_called_once()
        self.assertNotIn("'label': 'person'", output)


if __name__ == "__main__":
    unittest.main()
