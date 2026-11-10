# ESPAsyncTCP

ESP8266 maintenance fork of [ESP32Async/ESPAsyncTCP v2.0.0](https://github.com/ESP32Async/ESPAsyncTCP/tree/v2.0.0).
The original authors and LGPL license are preserved.

Version 2.0.1 fixes client destruction during `abort()`, accepted-byte reporting after output failures, empty-output polling, and retry/timeout handling for queued TCP output. Public method signatures and zero-copy defaults are unchanged.

Use this repository in PlatformIO `lib_deps` and pin a tested full commit SHA for reproducible firmware builds:

```ini
lib_deps =
  https://github.com/labodj/ESPAsyncTCP.git
```

## Verification

The native regression suite executes production method definitions against a controllable lwIP test double. It covers callback destruction, zero-byte output, accepted writes, full send queues, temporary output failures, persistent failure timeouts and clock rollover:

```sh
python3 -m unittest discover -s tests -v
CXX=clang++ python3 -m unittest discover -s tests -v
```

The tests use GCC or Clang with AddressSanitizer and UBSan. They test TCP contracts, not the radio or an emulated lwIP stack. CI also compiles all three included examples with ESP8266 Arduino core 3.1.2. With PlatformIO installed, `pio run -e esp8266` builds the server example; set `PLATFORMIO_SRC_DIR` to either other example directory to build it.

The inherited axTLS backend is disabled by default and is not covered by this maintenance work.

### Async TCP Library for ESP8266 Arduino

For ESP32 look [https://github.com/ESP32Async/AsyncTCP](https://github.com/ESP32Async/AsyncTCP)

This is a fully asynchronous TCP library, aimed at enabling trouble-free, multi-connection network environment for Espressif's ESP8266 MCUs.

This library is the base for [https://github.com/ESP32Async/ESPAsyncWebServer](https://github.com/ESP32Async/ESPAsyncWebServer)

## AsyncClient and AsyncServer
The base classes on which everything else is built. They expose all possible scenarios, but are really raw and require more skills to use.

## AsyncPrinter
This class can be used to send data like any other ```Print``` interface (```Serial``` for example).
The object then can be used outside of the Async callbacks (the loop) and receive asynchronously data using ```onData```. The object can be checked if the underlying ```AsyncClient```is connected, or hook to the ```onDisconnect``` callback.

## AsyncTCPbuffer
This class is really similar to the ```AsyncPrinter```, but it differs in the fact that it can buffer some of the incoming data.

## SyncClient
It is exactly what it sounds like. This is a standard, blocking TCP Client, similar to the one included in ```ESP8266WiFi```

## Libraries and projects that use AsyncTCP
- [ESP Async Web Server](https://github.com/ESP32Async/ESPAsyncWebServer)
- [Async MQTT client](https://github.com/marvinroger/async-mqtt-client)
- [arduinoWebSockets](https://github.com/Links2004/arduinoWebSockets)
- [ESP8266 Smart Home](https://github.com/baruch/esp8266_smart_home)
- [KBox Firmware](https://github.com/sarfata/kbox-firmware)
