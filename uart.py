from migen import *
from migen.fhdl import verilog


class ShiftOut(Module):
    def __init__(self):
        self.load = Signal(1)
        self.out_data = Signal(8)
        self.shift = Signal(1)

        self.empty = Signal(1, reset=1)
        self.overrun = Signal(1)

        count = Signal(max = 9)
        reg = Signal(10)

        self.tx = Signal(1)
        # Mux(self.empty, 1, reg[0])

        ###

        self.comb += [If(self.empty, self.tx.eq(1)).
                      Else(self.tx.eq(reg[0]))]

        self.sync += [
            If(self.load,
                If(self.empty,
                    reg[0].eq(0), reg[1:9].eq(self.out_data), reg[9].eq(1),
                    self.empty.eq(0),
                    self.overrun.eq(0),
                    count.eq(0)
                ).
                Else(
                    self.overrun.eq(1)
                )
            ),

            If(~self.empty & self.shift,
                reg[0:9].eq(reg[1:10]),
                reg[9].eq(0), # Zero out register as bits leave.
                If(count == 9,
                    self.empty.eq(1),
                    count.eq(0)
                ).
                Else(
                    count.eq(count + 1)
                )
            )
        ]


class ShiftIn(Module):
    def __init__(self):
        self.rx = Signal(1)
        self.sample = Signal(1) # Refine later to both sample and shift.
        self.shift = Signal(1)
        self.take = Signal(1)

        self.in_data = Signal(8)
        self.edge = Signal(1)
        self.empty = Signal(1, reset=1)
        self.busy = Signal(1)
        self.overrun = Signal(1)

        sync_rx = Signal(1)
        reg = Signal(9)
        rx_prev = Signal(1)
        count = Signal(max=9) # 1st-8th shift: data bits, 9th stop, 10th idle.

        ###

        self.comb += [self.edge.eq((rx_prev == 1) & (sync_rx == 0))]
        # self.comb += [reg[9].eq(sync_rx)]
        self.sync += [sync_rx.eq(self.rx)]
        self.sync += [rx_prev.eq(sync_rx)]

        self.sync += [
            If(self.take,
                self.empty.eq(1),
                self.overrun.eq(0)
            ),

            If(~self.busy & self.edge,
                self.busy.eq(1)
            ),

            If(self.shift & self.busy,
                reg[8].eq(sync_rx),
                reg[0:8].eq(reg[1:9]),
                If(count == 9,
                    # self.in_data.eq(reg[0:8]), # Shift test uses this.
                    self.in_data.eq(reg[1:9]),
                    count.eq(0),
                    self.busy.eq(0),
                    If(~self.empty, self.overrun.eq(1)).
                        Else(self.empty.eq(0))
                ).
                Else(
                    count.eq(count + 1)
                )
            )
        ]


class TimingGen(Module):
    # TODO: Programmable baud rate?
    def __init__(self, sys_clk=12000000, baud_rate=115200):
        # self.in_edge = Signal(1) #
        self.out_active = Signal(1)
        self.in_active = Signal(1)
        self.shift_out_strobe = Signal(1)
        self.shift_in_strobe = Signal(1)
        self.sysclk_factor = int(sys_clk/(baud_rate*16)) # TODO: Split clock domain.

        # print((sys_clk/(self.sysclk_factor*16) - baud_rate)/baud_rate)

        # self.sysclk_factor == 1 not currently supported.
        in_counter = Signal(max=self.sysclk_factor*16)
        out_counter = Signal(max=self.sysclk_factor*16)
        # in_hold = Signal(max=15)
        # out_hold = Signal(max=15) # Hold for 16 wraps of out_counter.

        self.sync += [
            out_counter.eq(0),
            in_counter.eq(0),

            If(self.in_active,
                self.shift_in_strobe.eq(0),
                in_counter.eq(in_counter + 1),
                If(in_counter == (self.sysclk_factor*8) - 1,
                    self.shift_in_strobe.eq(1)),
                If(in_counter == self.sysclk_factor*16 - 1,
                    in_counter.eq(0))
            ),

            If(self.out_active,
                self.shift_out_strobe.eq(0),
                out_counter.eq(out_counter + 1),
                If(out_counter == self.sysclk_factor*16 - 1,
                # If(out_counter == self.sysclk_factor - 1,
                    # out_hold.eq(out_hold + 1),
                    out_counter.eq(0), self.shift_out_strobe.eq(1))
                    # If(out_hold == 15, self.shift_out_strobe.eq(1)))
            )
            # .Else(
            #    out_hold.eq(0)
            # )
        ]


class Core(Module):
    def __init__(self, sys_clk=12000000, baud_rate=115200):
        self.out_data = Signal(8)
        self.in_data = Signal(8)
        self.tx = Signal(1)
        self.rx = Signal(1)
        self.wr = Signal(1)
        self.rd = Signal(1)
        self.tx_empty = Signal(1) # Also tx_busy.
        self.rx_empty = Signal(1)
        self.tx_ov = Signal(1)
        self.rx_ov = Signal(1)
        self.submodules.sout = ShiftOut()
        self.submodules.sin = ShiftIn()
        self.submodules.timing = TimingGen(sys_clk, baud_rate)

        ###

        # Propogate signals
        self.comb += [
            self.in_data.eq(self.sin.in_data),
            self.sout.out_data.eq(self.out_data),
            self.sin.take.eq(self.rd),
            self.sout.load.eq(self.wr),
            self.tx.eq(self.sout.tx),
            self.sin.rx.eq(self.rx),
            self.tx_empty.eq(self.sout.empty),
            self.rx_empty.eq(self.sin.empty),
            self.tx_ov.eq(self.sout.overrun),
            self.rx_ov.eq(self.sin.overrun)
        ]

        # Connect units
        self.comb += [
            self.sout.shift.eq(self.timing.shift_out_strobe),
            self.sin.shift.eq(self.timing.shift_in_strobe),
            self.timing.out_active.eq(~self.sout.empty),
            self.timing.in_active.eq(self.sin.busy)
        ]


class ShiftTest(Module):
    def __init__(self):
        self.submodules.sout = ShiftOut()
        self.submodules.sin = ShiftIn()

        ###

        self.comb += [
            self.sin.rx.eq(self.sout.tx),
        ]


class CoreTB(Module):
    def __init__(self, sys_clk=12000000, baud_rate=115200):
        self.submodules.core = Core(sys_clk, baud_rate)

        ###

        self.comb += [
            self.core.sin.rx.eq(self.core.sout.tx)
        ]


def toggle(sig):
    curr = (yield sig)
    if curr == 1:
        yield sig.eq(0)
    elif curr == 0:
        yield sig.eq(1)
    else:
        raise ValueError

def shift_tb(dut):
    # Add some dead time to more easily separate "inactive/active"
    for cyc in range(5):
        yield

    yield dut.sout.out_data.eq(0x55)
    yield dut.sout.load.eq(1)
    yield
    yield dut.sout.load.eq(0)
    yield # Not necessary, but delay so start bit lasts as long as other bits,
    # so we synchronize to start of shifting

    # Shift value as fast as possible
    for cyc in range(30):
        yield from toggle(dut.sout.shift)
        yield from toggle(dut.sin.shift)
        yield
    yield dut.sin.take.eq(1)
    yield
    yield dut.sin.take.eq(0)
    yield


def timing_tb(dut):
    # print((int(sys_clk/(baud_rate * 16))*baud_rate*16 - sys_clk)/sys_clk)
    # print(self.sysclk_factor)
    out_count = 0
    for cyc in range(5):
        yield

    yield dut.out_active.eq(1)
    yield dut.in_active.eq(1)
    yield

    for cyc in range(1000):
        if (yield dut.shift_out_strobe):
            out_count = out_count + 1
        if out_count == 10:
            break
        yield

    yield dut.out_active.eq(0)
    yield dut.in_active.eq(0)
    yield

    for cyc in range(5):
        yield


def core_tb(dut):
    # Add some dead time to more easily separate "inactive/active"
    for cyc in range(5):
        yield

    yield dut.core.sout.out_data.eq(0x55)
    yield dut.core.sout.load.eq(1)
    yield
    yield dut.core.sout.load.eq(0)
    yield # Not necessary, but delay so start bit lasts as long as other bits,
    # so we synchronize to start of shifting

    # Test send overrun
    for cyc in range(5):
        yield

    yield dut.core.sout.out_data.eq(0xAA)
    yield dut.core.sout.load.eq(1)
    yield
    yield dut.core.sout.load.eq(0)

    # Shift value as fast as possible
    for cyc in range(200):
        yield
        # if (yield dut.core.sin.busy) or ~(yield dut.core.sout.empty):
        #    yield
        # else:
        #    break

    yield dut.core.sout.out_data.eq(0xAA)
    yield dut.core.sout.load.eq(1)
    yield
    yield dut.core.sout.load.eq(0)

    # Test receive overrun
    for cyc in range(200):
        yield

    yield dut.core.sin.take.eq(1)
    yield
    yield dut.core.sin.take.eq(0)
    yield


if __name__ == "__main__":
    # dut = ShiftTest()
    # run_simulation(dut, shift_tb(dut), vcd_name="shift_tb.vcd")
    # dut = TimingGen(1843200, 115200)
    # run_simulation(dut, timing_tb(dut), vcd_name="timing_tb.vcd")
    # dut = CoreTB(1843200, 115200)
    # run_simulation(dut, core_tb(dut), vcd_name="core_tb.vcd")
    m = Core(12000000, 19200)
    with open("uart.v", "w") as fp:
        fp.write(str(verilog.convert(m, ios={m.tx, m.rx})))
