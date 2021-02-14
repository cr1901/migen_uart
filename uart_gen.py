from migen import If, Module, ClockSignal, ClockDomain
from migen.fhdl import verilog
from migen.fhdl.structure import Signal
from migen.genlib.io import CRG
from migen.build.generic_platform import Pins, Subsignal, IOStandard, ConstraintError

from fusesoc.capi2.generator import Generator
import importlib
import uart

class top(Module):
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
        self.loc_attrs = self.config.get('loc_attrs')

        migen_opts = self.config.get('migen')
        if migen_opts:
            self.platform = migen_opts.get('platform')
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
        m = top(self.clk_freq, self.baud_rate)

        try:
            module = "migen.build.platforms." + self.platform
            plat = importlib.import_module(module).Platform()
        except ModuleNotFoundError as e:
            print("Can't find platform " + self.platform)
            exit(1)

        if self.platform == "ice40_up5k_b_evn":
            # PMOD test.
            pmod_serial = [
                ("serial", 0,
                    Subsignal("rx", Pins("PMOD:6")),
                    Subsignal("tx", Pins("PMOD:5")),
                    Subsignal("rts", Pins("PMOD:4")),
                    Subsignal("cts", Pins("PMOD:7")),
                    IOStandard("LVCMOS33"),
                ),
            ]
            plat.add_extension(pmod_serial)

        serial = plat.request("serial")

        for led_mod in [m.tx_led, m.rx_led, m.load_led, m.take_led, m.empty_led]:
            try:
                led = plat.request("user_led")
                m.comb += led.eq(led_mod)
            except ConstraintError:
                continue

        m.comb += [
            serial.tx.eq(m.uart.tx),
            m.uart.rx.eq(serial.rx),
        ]

        plat.build(m, run=False, build_name="uart")
        return [{'build/uart.v' : {'file_type' : 'verilogSource'}},
            {'build/uart.pcf' : {'file_type' : 'PCF'}}]

    # Generate a design with loopback, but handle constraints outside of
    # migen.
    def gen_loopback_generic(self):
        m = top(self.clk_freq, self.baud_rate)

        # Mimic the platforms above and add a vendor-independent
        # Clock Reset Generator
        clk = Signal()
        m.submodules += CRG(clk)
        ios = {
                "tx" : m.uart.tx,
                "rx" : m.uart.rx,
                "tx_led" : m.tx_led,
                "rx_led" : m.rx_led,
                "load_led" : m.load_led,
                "take_led" : m.take_led,
                "empty_led" : m.empty_led,
                "clk" : clk
        }

        with open(self.output_file, "w") as fp:
            fp.write(str(verilog.convert(m, ios=set(ios.values()))))

        return [{'uart.v' : {'file_type' : 'verilogSource'}}]

    # Generate a core to be included in another project.
    def gen_core(self):
        m = uart.Core(self.clk_freq, self.baud_rate)

        ios = {m.tx, m.rx, m.out_data, m.in_data, m.wr, m.rd,
               m.tx_empty, m.rx_empty, m.tx_ov, m.rx_ov}

        with open(self.output_file, "w") as fp:
            fp.write(str(verilog.convert(m, ios=ios)))

        return [{'uart.v' : {'file_type' : 'verilogSource'}}]


ug = UartGenerator()
ug.run()
ug.write()
