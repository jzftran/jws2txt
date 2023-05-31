import unittest
import jws2txt
from jws2txt.helpers.helpers import frange
import csv
import os


test_file = 'test.txt'

class JWSFileTest(unittest.TestCase):

    def setUp(self) -> None:
        self.three_channels = jws2txt.JWSFile(r'tests/files/001Hg.jws')
        self.single_channel = jws2txt.JWSFile(r'tests/files/sample_fluorescence.jws')
        self.jwb_file = jws2txt.JWSFile(r'tests/files/2022_05_14-1.jwb')
    
    def test_three_channels_creation(self):
        # Test file creation and initialization
        
        self.assertEqual(self.three_channels.numchanels, 3)
        self.assertEqual(self.three_channels.npoints, 1201)
        self.assertEqual(self.three_channels.x_for_first_point, 320.0)
        self.assertEqual(self.three_channels.x_for_last_point, 200.0)
        self.assertEqual(self.three_channels.x_increment, -0.1)
        self.assertEqual(self.three_channels.header_codes, (268435715, 4097, 8193, 3))
        self.assertEqual(self.three_channels.header_names, ['WAVELENGTH', 'CD', 'HT VOLTAGE', 'ABSORBANCE'])  # noqa: E501
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
            
        # todo test for 1 ch file
        # todo test for saving

    def test_single_channel(self):
        # Test file creation and initialization
        
        self.assertEqual(self.single_channel.numchanels, 1)
        self.assertEqual(self.single_channel.npoints, 301)
        self.assertEqual(self.single_channel.x_for_first_point, 400.0)
        self.assertEqual(self.single_channel.x_for_last_point, 700.0)
        self.assertEqual(self.single_channel.x_increment, 1)
        self.assertEqual(self.single_channel.header_codes, (268435715, 14))
        self.assertEqual(self.single_channel.header_names, ['WAVELENGTH',
                                                            'FLUORESCENCE'])
        self.assertEqual(self.single_channel.data_list, [3,
                                                        1,
                                                        0,
                                                        1,
                                                        1,
                                                        301,
                                                        400.0,
                                                        700.0,
                                                        1.0,
                                                        268435715,
                                                        14,
                                                        268435715,
                                                        14,
                                                        400.0,
                                                        700.0,
                                                        700.0,
                                                        0.0])
        self.assertEqual(self.single_channel.sample_name, 'photonic wire')
        self.assertEqual(self.single_channel.comment, '')
        #test x-axis and 3 channels
        self.assertEqual(self.single_channel.unpacked_data[0][2], 402.0)
        self.assertEqual(self.single_channel.unpacked_data[1][2], 24.556852340698242)

    def test_jwb_file_creation(self):
        self.assertEqual(self.jwb_file.numchanels, 8)
        self.assertEqual(self.jwb_file.npoints, 1001)
        self.assertEqual(self.jwb_file.x_for_first_point, 900.0)
        self.assertEqual(self.jwb_file.x_for_last_point, 400.0)
        self.assertEqual(self.jwb_file.x_increment, -0.5)
        self.assertEqual(self.jwb_file.header_codes, (268435715, 3, 0, 8))
        self.assertEqual(self.jwb_file.header_names, ['WAVELENGTH', 'ABSORBANCE',
                                                       'undefined', 'undefined'])
        self.assertEqual(self.jwb_file.data_list, [3,
                                                    8,
                                                    1,
                                                    1,
                                                    1,
                                                    1001,
                                                    900.0,
                                                    400.0,
                                                    -0.5,
                                                    268435715,
                                                    3,
                                                    0,
                                                    8,
                                                    24.979999542236328,
                                                    60.0099983215332,
                                                    0.0,
                                                    2.00000035762821])
        self.assertEqual(self.jwb_file.sample_name, '')
        self.assertEqual(self.jwb_file.comment, '')
        # test x-axis and 3 channels
        self.assertEqual(self.jwb_file.unpacked_data[0][2], 899.0)
        # test 7th channel
        self.assertEqual(self.jwb_file.unpacked_data[7][2], 0.07367147505283356)
    
    def test_writing(self):
        self.three_channels.write_data(test_file)
        with open(test_file, 'r') as file:
             reader = csv.reader(file, dialect='excel')
             self.assertEqual(next(reader), ['HK14_CN'])
        os.remove(test_file)



class FrangeTest(unittest.TestCase):
     
    def test_frange(self):
        self.assertEqual(tuple(frange(1, 2, 0.2)), (1.0, 1.2, 1.4, 1.6, 1.8))
        self.assertEqual(tuple(frange(2, 0.9, -0.1)), (2.0, 1.9, 1.8, 1.7, 1.6, 1.5,
                                                        1.4, 1.2999999999999998, 1.2,
                                                        1.1, 1.0))






if __name__=='__main__':
	unittest.main()