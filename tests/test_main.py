import unittest
from jws2txt.jws2txt import str2bool
from argparse import ArgumentTypeError


class TestStr2Bool(unittest.TestCase):
     
     def test_str2bool(self):
          self.assertTrue(str2bool('y'))
          self.assertTrue(str2bool('true'))
          self.assertFalse(str2bool('n'))
          self.assertFalse(str2bool('f'))
          with self.assertRaises(ArgumentTypeError):
               str2bool('blurb')



if __name__=='__main__':
	unittest.main()