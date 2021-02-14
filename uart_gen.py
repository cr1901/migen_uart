from migen import If, Module, ClockSignal, ClockDomain
from migen.fhdl import verilog
from migen.fhdl.structure import Signal
from migen.genlib.io import CRG
from migen.build.generic_platform import Pins, Subsignal, IOStandard, ConstraintError

from fusesoc.capi2.generator import Generator
import importlib
import uart

class LoopbackTop(Module):
    def __init__(self, clk_freq, baud_rate):
        self.submodules.uart = uart.Core(clk_freq, baud_rate)

        self.rx_led = Signal()
        self.tx_led = Signal()
        self.load_led = Signal()
        self.take_led = Signal()
        self.empty_led = Signal()
        self.comb += [self.tx_led.eq(~self.uart.tx),
                      self.rx_led.eq(~self.uart.rx),
                      self.load_led.eq(self.uart.sout.load),
                      self.take_led.eq(self.uart.sin.take),
                      self.empty_led.eq(self.uart.sin.empty)]
        self.comb += [self.uart.out_data.eq(self.uart.in_data)]

        self.sync += [
            self.uart.wr.eq(0),
            self.uart.rd.eq(0),
            If(~self.uart.sin.empty,
               self.uart.wr.eq(1),
               self.uart.rd.eq(1)
            )
        ]

class UartGenerator(Generator):
    output_file = "uart.v"

    def __init__(self):
        super().__init__()
        self.clk_freq  = self.config.get('clk_freq', 12000000)
        self.baud_rate = self.config.get('baud_rate', 19200)
        self.loopback = self.config.get('loopback')

        migen_opts = self.config.get('migen')
        if migen_opts:
            self.platform = migen_opts.get('platform')
            self.extensions = migen_opts.get('extensions')
        else:
            self.platform = None

    def run(self):
        if self.loopback:
            if self.platform:
                files = self.gen_loopback_platform()
            else:
                files = self.gen_loopback_generic()
        else:
            files = self.gen_core()

        self.add_files(files)

    # Generate a design with loopback, but handle constraints within migen.
    def gen_loopback_platform(self):
        m = LoopbackTop(self.clk_freq, self.baud_rate)

        try:
            module = "migen.build.platforms." + self.platform
            plat = importlib.import_module(module).Platform()
        except ModuleNotFoundError as e:
            print("Can't find platform " + self.platform)
            exit(1)

        exts = self.mk_extensions()
        if exts:
            plat.add_extension(exts)

        serial = plat.request("serial")
        m.comb += [
            serial.tx.eq(m.uart.tx),
            m.uart.rx.eq(serial.rx),
        ]

        for led_mod in [m.tx_led, m.rx_led, m.load_led, m.take_led, m.empty_led]:
            try:
                led = plat.request("user_led")
                m.comb += led.eq(led_mod)
            except ConstraintError:
                continue

        plat.build(m, run=False, build_name="uart")
        return [{'build/uart.v' : {'file_type' : 'verilogSource'}},
            {'build/uart.pcf' : {'file_type' : 'PCF'}}]

    # Generate a design with loopback, but handle constraints outside of
    # migen.
    def gen_loopback_generic(self):
        m = LoopbackTop(self.clk_freq, self.baud_rate)

        # Mimic the platforms above and add a vendor-independent
        # Clock Reset Generator
        clk = Signal()
        m.submodules += CRG(clk)
        ios = {m.uart.tx, m.uart.rx, m.tx_led, m.rx_led, m.load_led,
               m.take_led, m.empty_led, clk}

        with open(self.output_file, "w") as fp:
            fp.write(str(verilog.convert(m, ios=ios, name="uart")))

        return [{'uart.v' : {'file_type' : 'verilogSource'}}]

    # Generate a core to be included in another project.
    def gen_core(self):
        m = uart.Core(self.clk_freq, self.baud_rate)

        ios = {m.tx, m.rx, m.out_data, m.in_data, m.wr, m.rd,
               m.tx_empty, m.rx_empty, m.tx_ov, m.rx_ov}

        with open(self.output_file, "w") as fp:
            fp.write(str(verilog.convert(m, ios=ios, name="uart")))

        return [{'uart.v' : {'file_type' : 'verilogSource'}}]

    # Convert YAML description of migen extensions to what the build system
    # expects.
    def mk_extensions(self):
        ext_list = None

        if self.extensions:
            ext_list = []
            for name, ext_data in self.extensions.items():
                if name not in ("serial", "user_led"):
                    print("extensions must be one of \"serial\" or \"user_led\"")
                    exit(2)

                ext_count = 0
                # Extensions can have more than one instance.
                for inst in ext_data:
                    subsignals = []
                    pins = []
                    io_standard = []

                    pins_cfg = inst.get("pins")
                    subsig_cfg = inst.get("subsignals")
                    io_cfg = inst.get("io_standard")

                    if pins_cfg is not None and subsig_cfg is not None:
                        print("extensions must contain \"pins\" or \"subsignals\", but not both")
                        exit(3)

                    if pins_cfg:
                        pins.append(Pins(pins_cfg))

                    if subsig_cfg:
                        for sub_name, sub_data in subsig_cfg.items():
                            subsignals.append(Subsignal(sub_name, Pins(sub_data["pins"])))

                            # io_standard on subsignal not supported yet.

                    if io_cfg:
                        io_standard.append(IOStandard(io_cfg))

                    ext_list.append((name, ext_count, *pins, *subsignals, *io_standard))
                    ext_count = ext_count + 1

        return ext_list


ug = UartGenerator()
ug.run()
ug.write()
