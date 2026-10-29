import unittest
from nanoka_viewer.api.models import get_element, get_element_image

class LumifluxElementTest(unittest.TestCase):
    def test_lumiflux_mapping(self):
        char_data = {"element": 300}
        self.assertEqual(get_element("zzz", char_data), "Lumiflux")
        url = get_element_image("zzz", char_data)
        self.assertTrue(url.endswith("IconLumiflux.webp"))

if __name__ == "__main__":
    unittest.main()
