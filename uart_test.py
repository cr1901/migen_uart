from migen import *
from migen.build.generic_platform import Pins
from migen.build.platforms import icestick

import uart

class top(Module):
    def __init__(self):
        self.submodules.uart = uart.Core(12000000, 19200)

if __name__ == "__main__":
    m = top()

    plat = icestick.Platform()
    serial = plat.request("serial")
    rx_led = plat.request("user_led")
    tx_led = plat.request("user_led")
    load_led = plat.request("user_led")
    take_led = plat.request("user_led")
    empty_led = plat.request("user_led")
    m.comb += [tx_led.eq(~serial.tx), rx_led.eq(~serial.rx),
        load_led.eq(m.uart.sout.load), take_led.eq(m.uart.sin.take),
        empty_led.eq(m.uart.sin.empty)]
    m.comb += [serial.tx.eq(m.uart.tx)]
    m.comb += [m.uart.rx.eq(serial.rx)]

    # Doesn't work!
    # m.comb += [m.uart.sout.out_data.eq(m.uart.sin.in_data)]
    #
    # m.sync += [
    #     m.uart.sout.load.eq(0),
    #     m.uart.sin.take.eq(0),
    #     If(~m.uart.sin.empty,
    #         m.uart.sout.load.eq(1),
    #         m.uart.sin.take.eq(1)
    #     )
    # ]

    m.comb += [m.uart.out_data.eq(m.uart.in_data)]

    m.sync += [
        m.uart.wr.eq(0),
        m.uart.rd.eq(0),
        If(~m.uart.sin.empty,
            m.uart.wr.eq(1),
            m.uart.rd.eq(1)
        )
    ]

    # plat.add_period_constraint(m.cd_sys.clk, 1000/12.0)
    plat.build(m, run=True, build_name="uart")
    prog = plat.create_programmer()
    prog.flash(0, "build/uart.bin")
