# ========================================================================== #
#                                                                            #
#    KVMD - The main Pi-KVM daemon.                                          #
#                                                                            #
#    Copyright (C) 2020  Maxim Devaev <mdevaev@gmail.com>                    #
#                                                                            #
#    This program is free software: you can redistribute it and/or modify    #
#    it under the terms of the GNU General Public License as published by    #
#    the Free Software Foundation, either version 3 of the License, or       #
#    (at your option) any later version.                                     #
#                                                                            #
#    This program is distributed in the hope that it will be useful,         #
#    but WITHOUT ANY WARRANTY; without even the implied warranty of          #
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the           #
#    GNU General Public License for more details.                            #
#                                                                            #
#    You should have received a copy of the GNU General Public License       #
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.  #
#                                                                            #
# ========================================================================== #


import asyncio
import struct

from typing import Tuple
from typing import Any

from .errors import RfbConnectionError


# =====
class RfbClientStream:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.__reader = reader
        self.__writer = writer

        self._remote = "[%s]:%d" % (self.__writer.transport.get_extra_info("peername")[:2])

    # =====

    async def _read_number(self, fmt: str) -> int:
        assert len(fmt) == 1
        try:
            if fmt == "B":
                return (await self.__reader.readexactly(1))[0]
            else:
                fmt = f">{fmt}"
                return struct.unpack(fmt, await self.__reader.readexactly(struct.calcsize(fmt)))[0]
        except (ConnectionError, asyncio.IncompleteReadError) as err:
            raise RfbConnectionError(err)

    async def _read_struct(self, fmt: str) -> Tuple[int, ...]:
        assert len(fmt) > 1
        try:
            fmt = f">{fmt}"
            return struct.unpack(fmt, (await self.__reader.readexactly(struct.calcsize(fmt))))
        except (ConnectionError, asyncio.IncompleteReadError) as err:
            raise RfbConnectionError(err)

    async def _read_text(self, length: int) -> str:
        try:
            return (await self.__reader.readexactly(length)).decode("utf-8", errors="ignore")
        except (ConnectionError, asyncio.IncompleteReadError) as err:
            raise RfbConnectionError(err)

    # =====

    async def _write_struct(self, fmt: str, *values: Any, drain: bool=True) -> None:
        try:
            if not fmt:
                for value in values:
                    self.__writer.write(value)
            elif fmt == "B":
                assert len(values) == 1
                self.__writer.write(bytes([values[0]]))
            else:
                self.__writer.write(struct.pack(f">{fmt}", *values))
            if drain:
                await self.__writer.drain()
        except ConnectionError as err:
            raise RfbConnectionError(err)

    async def _write_reason(self, text: str, drain: bool=True) -> None:
        encoded = text.encode("utf-8", errors="ignore")
        await self._write_struct("L", len(encoded), drain=False)
        try:
            self.__writer.write(encoded)
            if drain:
                await self.__writer.drain()
        except ConnectionError as err:
            raise RfbConnectionError(err)

    async def _write_fb_update(self, width: int, height: int, encoding: int, drain: bool=True) -> None:
        await self._write_struct(
            "BxH HH HH l",
            0,  # FB update
            1,  # Number of rects
            0, 0, width, height, encoding,
            drain=drain,
        )

    # =====

    def _close(self) -> None:
        try:
            self.__writer.close()
        except Exception:
            pass
