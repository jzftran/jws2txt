import argparse
import os
from .helpers.helpers import JWSFile


def str2bool(v) -> bool:
    """Converts string to bool."""
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

def main():
    
    parser = argparse.ArgumentParser(description='Converts *.jws or *jwb files to human\
                                     -readable text files.')
    parser.add_argument('--in-path', type=str, required=True,
                        help="Path to file or folder containing files for conversion.")
    parser.add_argument('--out-dir', type=str,  help='Output folder')
    parser.add_argument('--delimiter', type=str, default='\t', help='Delimiter used in\
                         saved text files.')
    parser.add_argument('--comments', type=str2bool, choices=[True, False], default=True,  # noqa: E501
                         help='Write sample information.')
    parser.add_argument('--header', type=str2bool, choices=[True, False], default=True,
                         help='Write header.')

    args = parser.parse_args()

    if not os.path.exists(args.in_path):
        raise FileNotFoundError(f"{args.in_path} does not exist.")

    if args.out_dir is None:
        args.out_dir = args.in_path

    if not os.path.exists(args.out_dir):
        os.mkdir(args.out_dir)

    for (root, dirs, files) in os.walk(args.in_path, topdown=True):
        gen = (file for file in files if file.endswith(('.jwb', '.jws')))

        for file in gen:

            out_file_path = os.path.join(args.out_dir, ''.join((os.path.splitext(file)[0],  # noqa: E501
                                                                 '.txt')))
            jws_file_path = os.path.join(root, file)

            JWSFile(path=jws_file_path).write_data(out_file=out_file_path,
                                                   delimiter=args.delimiter,
                                                   write_comments=args.comments,
                                                   write_header=args.header)
      

if __name__ == '__main__':
    main()
