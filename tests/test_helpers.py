import unittest
import jws2txt

class JWSFileTest(unittest.TestCase):

    def setUp(self) -> None:
        self.three_channels = jws2txt.JWSFile(r'tests/files/001Hg.jws')
        

    def test_three_channels_creation(self):
        # Test file creation and initialization
        
        self.assertEqual(self.three_channels.numchanels, 3)
        self.assertEqual(self.three_channels.npoints, 1201)
        self.assertEqual(self.three_channels.x_for_first_point, 320.0)
        self.assertEqual(self.three_channels.x_for_last_point, 200.0)
        self.assertEqual(self.three_channels.x_increment, -0.1)
        self.assertEqual(self.three_channels.header_codes, (268435715, 4097, 8193, 3))
        self.assertEqual(self.three_channels.header_names, ['WAVELENGTH', 'CD', 'HT VOLTAGE', 'ABSORBANCE'])
        self.assertEqual(self.three_channels.data_list, [3,
                                                        1,
                                                        0,
                                                        3,
                                                        1,
                                                        1201,
                                                        320.0,
                                                        200.0,
                                                        -0.1,
                                                        268435715,
                                                        4097,
                                                        8193,
                                                        3,
                                                        8.6939493804496e-311,
                                                        200.0,
                                                        1.0,
                                                        320.0])
        self.assertEqual(self.three_channels.sample_name, 'HK14_CN')
        self.assertEqual(self.three_channels.comment, '1mm')
        #test x-axis and 3 channels
        self.assertEqual(self.three_channels.unpacked_data[0][2], 319.8)
        self.assertEqual(self.three_channels.unpacked_data[1][2], 0.1975005567073822)
        self.assertEqual(self.three_channels.unpacked_data[2][2], 206.2129669189453)
        self.assertEqual(self.three_channels.unpacked_data[3][2], 0.11851496249437332)
            

if __name__=='__main__':
	unittest.main()