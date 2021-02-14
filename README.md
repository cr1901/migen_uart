# `migen_uart`
`migen_uart` is a minimal UART meant for no-hassle testing purposes and an
example of integrating [`fusesoc`](https://github.com/olofk/fusesoc) with
[`migen`](https://github.com/m-labs/migen) via the former's generator API
(GAPI 1.0).

## Quick Start
Initialize the `fusesoc` library and make sure `fusesoc` sees the
`migen_uart_gen` generator and `migen_uart` and sample `loopback` cores:

```
fusesoc library add migen_uart .
fusesoc list-cores
fusesoc gen list
```

Generate a loopback core for the [iCEBreaker](https://github.com/icebreaker-fpga/icebreaker)
and program the bitstream:

```
fusesoc run --target icebreaker cr1901:migen:uart-loopback
iceprog build/cr1901_migen_uart-loopback_0/icebreaker-icestorm/cr1901_migen_uart-loopback_0.bin
```

Once the above is done, open a serial terminal at 19,200 baud connecting to the
iCEBreaker. If you type characters and see them echo'd back, congratulations,
you have successfully used the loopback core provided w/ this library!

Take a look at `loopback/loopback.core` as well as the help from `fusesoc gen show migen_uart_gen`
for examples on how to use the `migen_uart` core (which only provides the
generator at present, and nothing else)!

## Clean
Assuming you are in your working directory with `fusesoc.conf`, you can clean
your work tree by running:

```
rm -rf fusesoc.conf build/ fusesoc_libraries
```
