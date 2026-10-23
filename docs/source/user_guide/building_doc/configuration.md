(fabric-configuration)=
# Fabric configuration

FABulous fabrics offer a 32-bit wide configuration port which can either be driven directly by e.g. a CPU or bus or by the configuration adapters, allowing the transmission over UART or SPI and a custom bitbang protocol.

## Parallel Port

Configuration data is written directly into the fabric through a 32-bit
parallel port, rather than shifted in bit-serially. This is the main configuration interface which is also used by the UART and bitbang configuration adapters.

- **Signals:** `SelfWriteData` (32-bit data bus), `SelfWriteStrobe` (write strobe)
- **Bus width:** 32 bits - each transfer loads 4 bytes of the bitstream
- **Timing:** Data must be valid on the bus for at least one clock cycle before `SelfWriteStrobe` is asserted, and held stable while the strobe is high.

## Configuration Adapters

To allow configuration from outside of a chip, a serial adapter (UART or SPI, selected by the `ConfigInterface` fabric parameter) and a bitbang adapter are implemented. The serial adapter has priority over bitbang, bitbang over the parallel port.

###  UART

The configuration is sent to the fabric bit-by-bit over a UART link on `Rx` (since the adapter does not transmit anything, it's technically just a "UAR"),
decoded, and assembled into 32-bit words that feed the configuration port.

- **Signals:** `Rx` (UART input), `WriteData` (32-bit, output to the parallel
  config port), `WriteStrobe`, `Command` (decoded command byte), `ComActive`,
  `ReceiveLED`
- **Frame format:** standard UART frame — 1 start bit, 8 data bits, 1 stop bit
- **Baud rate:** set by `ComRate = f_CLK / Baudrate` (default `217`, e.g. 25 MHz / 115200 baud)
- **Encoding modes:** `auto`, `hex` (2 ASCII hex chars per byte), or `bin`
  (raw byte), selected by the `Mode` parameter or auto-detected from the
  command byte
- **Framing:** each transfer begins with a fixed ID header and a command
  byte before data bytes are accepted
- **Word assembly:** 4 received bytes are packed into one `WriteData` word,
  then `WriteStrobe` pulses once per word, as the configuration interface expects
- **Integrity check:** a running checksum is accumulated over the data and
  validated against an expected checksum value
- **Timeout:** an inactivity timeout resets the receiver to idle if no data
  arrives mid-transfer

### SPI

With `ConfigInterface,SPI` in `fabric.csv`, `fabric_spi_receiver` replaces the UART. It is a plain SPI receiver: no header, command or checksum, the bitstream file is sent as it is.

- **Signals:** `SPI_SCLK`, `SPI_CS_N` (active low), `SPI_MOSI`, `SPI_MISO` (always `0`), `ComActive` (high while `SPI_CS_N` is asserted), `ReceiveLED`
- **Mode:** SPI mode 1 (CPOL 0, CPHA 1): MOSI changes on the rising SCLK edge and is sampled on the falling edge, MSB first
- **Clock:** SCLK, CS and MOSI are synchronised to `CLK`, so SCLK must stay well below `CLK`; a half period of two `CLK` cycles works in simulation
- **Word assembly:** every 32 bits form one word, written to the configuration port in the byte order of the bitstream file
- **Alignment:** the bit counter is only cleared by `resetn`, not by `SPI_CS_N`; always send whole 32-bit words
- **Resync:** asserting `SPI_CS_N` restarts the search for the `0xFAB0FAB1` sync word, like `ComActive` of the UART

:::{note}
The selection is written into the generated `eFPGA_top.v` as a fixed `ConfigInterface` value on the `eFPGA_Config` instance, not as a parameter of `eFPGA_top`, so any flow that synthesises `eFPGA_top` picks it up automatically. Always synthesise the configuration logic through `eFPGA_top`: synthesising `eFPGA_Config` on its own (as its own top or macro) ignores the selection and silently builds the `UART` default.
:::

### Bitbang

The bitbang adapter offers a quick asynchronous serial configuration port interface that is ideal for configuring the fabric via a microcontroller. The idea of the protocol is as follows:

:::{figure} ./figs/bitbang1.*
:align: center
:alt: Bitbang description
:::

- **Signals:** `s_clk` and `s_data`, as well as a one-cycle strobe output (active 1).
- **Protocol:** Data is sampled on each rising edge of `s_clk`, and control is sampled on the falling edge.
- **Word assembly:** Both values get shifted in a separate register; if the control register sees the bit-pattern x"FAB0", it samples the data shift register into a hold register and issues a one-cycle strobe output (active 1).

The next figure shows the enable generation (and input sampling) for generating the enable signals for

- the control shift register and
- the data shift register.

:::{figure} ./figs/bitbang2.*
:align: center
:alt: An illustration of the signals used in the custom bitbang protocol as well as the decoding of these signals.
:::
