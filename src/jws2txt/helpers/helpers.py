from struct import unpack
import csv
import olefile as ofio


DATAINFO_FMT = '<LLLLLLdddLLLLdddd'

CHANNELS_DEFINITIONS = {
    536871427: "TIME",
    268435715: "WAVELENGTH",
    4097: "CD",
    8193: "HT VOLTAGE",
    3: "ABSORBANCE",
    14: "FLUORESCENCE"
}


def frange(start: float, stop: float = 0, step: float = 1.0):
    """Return evenly spaced number over specified range.

    Args:
        start (float): The starting value of the sequence.
        stop (float): The last value of the sequence.
        step (float): The step for which the sequence is generated.
        """

    count = 0
    while True:
        range = start + count * step
        if step > 0 and range >= stop:
            break
        elif step < 0 and range <= stop:
            break
        yield range
        count += 1


class JWSFile:
    """Representation of the JASCO JWS or JWB file."""

    def __init__(self, file: ofio.olefile.OleFileIO) -> None:
        """Initializes the JWSFile class.

        Args:
           file (olefile.olefile.OleFileIO): JWS or JWB file read by OleFileIO
        """
        data_info = file.openstream('DataInfo').read()

        if (len(data_info)) < 96:
            raise Exception("DataInfo should be at least 96 bytes!")

        data_info = data_info[:96]
        data_tuple = unpack(DATAINFO_FMT, data_info)
        self.numchanels = data_tuple[3]
        self.npoints = data_tuple[5]
        self.x_for_first_point = data_tuple[6]
        self.x_for_last_point = data_tuple[7]
        self.x_increment = data_tuple[8]

        self.header_codes = tuple([x for i, x in enumerate(data_tuple[9:13]) if x not in data_tuple[9:13][:i]])

        self.header_names = [CHANNELS_DEFINITIONS.get(k, "undefined") for k in self.header_codes]

        self.data_list = list(data_tuple)

        if not file.exists('Y-Data'):
            raise Exception("Y-Data not found!")

        y_data = file.openstream('Y-Data').read()

        # data format
        fmt = 'f'*self.npoints

        try:
            self.unpack_y_data(y_data, format=fmt, num_chanels=self.numchanels)

        except:
            try:
                # works in the case of *.jwb file
                self.numchanels = data_tuple[1]
                self.unpack_y_data(y_data, format=fmt, num_chanels=self.numchanels)
            except:
                print("Incorrect number of channels.")

        sample_info = file.openstream('SampleInfo').read()[8:].split(b'\x00\x00\x08\x00')

        try:
            self.decode_sample_info(sample_info)
        except:
            self.sample_name = ''
            self.comment = ''

    def unpack_y_data(self, y_data: bytes, format: str, num_chanels: int) -> None:
        """Unpacks the Y-Data from the JWS file.
        """
        chunk_size = int(len(y_data)/num_chanels)
        data_chunked = [y_data[i:i + chunk_size] for i in range(0, len(y_data), chunk_size)]
        unpacked_data = [unpack(format, data_chunk) for data_chunk in data_chunked]
        # generate x_data
        x_data = frange(self.x_for_first_point,
                        self.x_for_last_point + self.x_increment,
                        self.x_increment)

        unpacked_data.insert(0, tuple(x_data))
        self.unpacked_data = unpacked_data

    def decode_sample_info(self, sample_info_bytes: list) -> None:
        """Decodes the SampleInfo"""
        if len(sample_info_bytes) == 2:
            sample_name = sample_info_bytes[0].split(b'\x00\x00')[0]
            self.sample_name = (self.unpack_sample_info(sample_name))

            comment = sample_info_bytes[1].split(b'\x00\x00')[1]
            self.comment = self.unpack_sample_info(comment)

        elif len(sample_info_bytes) == 1:
            sample_name = sample_info_bytes[0].split(b'\x00\x00')[0]
            self.sample_name = self.unpack_sample_info(sample_name)

            self.comment = ''

    def unpack_sample_info(self, packed_bytes: bytes) -> str:
        """Unpacks SampleInfo bytes"""
        if packed_bytes[-1:] not in {b'\x00', b''}:
            packed_bytes += b'\x00'
        format_specifier = f'{len(packed_bytes)}s'
        unpacked_str = unpack(format_specifier, packed_bytes)[0].decode('utf16')
        return (unpacked_str)

    def write_data(self, out_file: str,
                   write_comments: bool = True,
                   write_header: bool = True,
                   delimiter: str = '\t') -> None:

        values = zip(*self.unpacked_data)
        try:
            with open(out_file, 'x', newline='') as f:
                writer = csv.writer(f, delimiter=delimiter)

                if write_comments == True:
                    writer.writerow([self.sample_name])
                    writer.writerow([self.comment])

                if write_header == True:
                    if len(self.header_names) == len(self.unpacked_data):
                        writer.writerow(self.header_names)
                    elif len(self.header_names) < len(self.unpacked_data):
                        diff = len(self.unpacked_data)-len(self.header_names)
                        self.header_names.extend([self.header_names[-1]]*diff)
                        writer.writerow(self.header_names)

                writer.writerows(values)
        except  FileExistsError:
            print(f"Error: File '{out_file}' already exists.")

