"""Minimal ctypes wrapper for XEditLib.dll used by VNV Korean Patcher."""
from __future__ import annotations

import ctypes
from ctypes import c_uint8, c_uint16, c_uint32, c_int32, c_void_p, byref
from pathlib import Path
import time


class XEditError(RuntimeError):
    pass


class XEditLib:
    GM_FNV = 0

    def __init__(self, dll_path: Path):
        self.dll_path = Path(dll_path).resolve()
        self.dll = ctypes.WinDLL(str(self.dll_path))
        self._bind_all()

    def _bind(self, name, restype, *argtypes):
        fn = getattr(self.dll, name)
        fn.restype = restype
        fn.argtypes = list(argtypes)
        setattr(self, "_raw_" + name, fn)

    def _bind_all(self):
        W = ctypes.c_wchar_p
        V = c_void_p
        U16 = c_uint16
        U32 = c_uint32
        I32 = c_int32
        U8 = c_uint8
        self._bind("InitXEdit", None)
        self._bind("CloseXEdit", None)
        self._bind("GetResultString", U16, V, I32)
        self._bind("GetResultArray", U16, V, I32)
        self._bind("GetExceptionMessageLength", None, V)
        self._bind("GetExceptionStackLength", None, V)
        self._bind("Release", U16, U32)
        self._bind("SetGamePath", U16, W)
        self._bind("SetLanguage", U16, W)
        self._bind("SetGameMode", U16, I32)
        self._bind("LoadPlugins", U16, W, U16, U16)
        self._bind("GetLoaderStatus", U16, V)
        self._bind("FileByName", U16, W, V)
        self._bind("SaveFile", U16, U32, W)
        self._bind("GetMasterNames", U16, U32, V)
        self._bind("HasElement", U16, U32, W, V)
        self._bind("GetElement", U16, U32, W, V)
        self._bind("GetElements", U16, U32, W, U16, U16, U16, V)
        self._bind("GetElementFile", U16, U32, V)
        self._bind("GetElementGroup", U16, U32, V)
        self._bind("ElementType", U16, U32, V)
        self._bind("ValueType", U16, U32, V)
        self._bind("ElementToJson", U16, U32, V)
        self._bind("Name", U16, U32, V)
        self._bind("Path", U16, U32, U16, U16, U16, V)
        self._bind("PathName", U16, U32, U16, V)
        self._bind("Signature", U16, U32, V)
        self._bind("GetValue", U16, U32, W, V)
        self._bind("SetValue", U16, U32, W, W)
        self._bind("GetFlag", U16, U32, W, W, V)
        self._bind("SetFlag", U16, U32, W, W, U16)
        self._bind("GetFormID", U16, U32, V, U16)
        self._bind("GetRecords", U16, U32, W, U16, V)
        self._bind("GetOverrides", U16, U32, V)
        self._bind("GetMasterRecord", U16, U32, V)
        self._bind("IsMaster", U16, U32, V)

    def _result_string(self, caller) -> str:
        length = c_int32(0)
        if not caller(byref(length)):
            self._fail("String operation failed")
        if length.value < 1:
            return ""
        buf = ctypes.create_unicode_buffer(length.value)
        if not self._raw_GetResultString(buf, length.value):
            self._fail("GetResultString failed")
        return buf.value

    def _result_array(self, caller) -> list[int]:
        length = c_int32(0)
        if not caller(byref(length)):
            self._fail("Array operation failed")
        if length.value < 1:
            return []
        arr = (c_uint32 * length.value)()
        if not self._raw_GetResultArray(arr, length.value):
            self._fail("GetResultArray failed")
        return list(arr)

    def _result_handle(self, caller) -> int:
        out = c_uint32(0)
        if not caller(byref(out)):
            self._fail("Handle operation failed")
        return out.value

    def _result_bool(self, caller) -> bool:
        out = c_uint16(0)
        if not caller(byref(out)):
            self._fail("Boolean operation failed")
        return bool(out.value)

    def _result_byte(self, caller) -> int:
        out = c_uint8(0)
        if not caller(byref(out)):
            self._fail("Byte operation failed")
        return out.value

    def _exception_text(self, length_fn) -> str:
        try:
            length = c_int32(0)
            length_fn(byref(length))
            if length.value < 1:
                return ""
            buf = ctypes.create_unicode_buffer(length.value)
            if self._raw_GetResultString(buf, length.value):
                return buf.value
        except Exception:
            pass
        return ""

    def _fail(self, message: str):
        detail = self._exception_text(self._raw_GetExceptionMessageLength)
        stack = self._exception_text(self._raw_GetExceptionStackLength)
        raise XEditError("\n".join(x for x in (message, detail, stack) if x))

    def init(self):
        self._raw_InitXEdit()

    def close(self):
        self._raw_CloseXEdit()

    def release(self, handle: int):
        if handle:
            self._raw_Release(handle)

    def set_game_path(self, path: str):
        if not self._raw_SetGamePath(path):
            self._fail("SetGamePath failed")

    def set_language(self, language: str):
        if not self._raw_SetLanguage(language):
            self._fail("SetLanguage failed")

    def set_game_mode(self, mode: int):
        if not self._raw_SetGameMode(mode):
            self._fail("SetGameMode failed")

    def load_plugins(self, plugins: str, smart_load=True, build_refs=False):
        if not self._raw_LoadPlugins(plugins, int(smart_load), int(build_refs)):
            self._fail("LoadPlugins failed")

    def wait_for_loader(self, timeout=180.0):
        deadline = time.monotonic() + timeout
        while True:
            status = self._result_byte(lambda out: self._raw_GetLoaderStatus(out))
            if status == 2:
                return
            if status == 3:
                self._fail("Loader failed")
            if time.monotonic() > deadline:
                raise TimeoutError("XEditLib loader timeout")
            time.sleep(0.25)

    def file_by_name(self, name: str) -> int:
        return self._result_handle(lambda out: self._raw_FileByName(name, out))

    def save_file(self, handle: int, path: str):
        if not self._raw_SaveFile(handle, path):
            self._fail("SaveFile failed")

    def get_master_names(self, handle: int) -> list[str]:
        text = self._result_string(lambda out: self._raw_GetMasterNames(handle, out))
        return [x for x in text.split("\r\n") if x]

    def has_element(self, handle: int, path="") -> bool:
        return self._result_bool(lambda out: self._raw_HasElement(handle, path, out))

    def get_element(self, handle: int, path="") -> int:
        return self._result_handle(lambda out: self._raw_GetElement(handle, path, out))

    def get_elements(self, handle: int, path="", sort=False, filter=False, sparse=False) -> list[int]:
        return self._result_array(
            lambda out: self._raw_GetElements(handle, path, int(sort), int(filter), int(sparse), out))

    def get_element_file(self, handle: int) -> int:
        return self._result_handle(lambda out: self._raw_GetElementFile(handle, out))

    def get_element_group(self, handle: int) -> int:
        return self._result_handle(lambda out: self._raw_GetElementGroup(handle, out))

    def element_type(self, handle: int) -> int:
        return self._result_byte(lambda out: self._raw_ElementType(handle, out))

    def value_type(self, handle: int) -> int:
        return self._result_byte(lambda out: self._raw_ValueType(handle, out))

    def element_to_json(self, handle: int) -> str:
        return self._result_string(lambda out: self._raw_ElementToJson(handle, out))

    def name(self, handle: int) -> str:
        return self._result_string(lambda out: self._raw_Name(handle, out))

    def path(self, handle: int, short=False, local=False, sort=False) -> str:
        return self._result_string(
            lambda out: self._raw_Path(handle, int(short), int(local), int(sort), out))

    def path_name(self, handle: int, short=False) -> str:
        return self._result_string(lambda out: self._raw_PathName(handle, int(short), out))

    def signature(self, handle: int) -> str:
        return self._result_string(lambda out: self._raw_Signature(handle, out))

    def get_value(self, handle: int, path="") -> str:
        return self._result_string(lambda out: self._raw_GetValue(handle, path, out))

    def set_value(self, handle: int, path: str, value: str):
        if not self._raw_SetValue(handle, path, value):
            self._fail("SetValue failed")

    def get_flag(self, handle: int, path: str, name: str) -> bool:
        return self._result_bool(lambda out: self._raw_GetFlag(handle, path, name, out))

    def set_flag(self, handle: int, path: str, name: str, enabled: bool):
        if not self._raw_SetFlag(handle, path, name, int(enabled)):
            self._fail("SetFlag failed")

    def get_form_id(self, handle: int, local=False) -> int:
        out = c_uint32(0)
        if not self._raw_GetFormID(handle, byref(out), int(local)):
            self._fail("GetFormID failed")
        return out.value

    def get_records(self, handle: int, search="", include_overrides=False) -> list[int]:
        return self._result_array(
            lambda out: self._raw_GetRecords(handle, search, int(include_overrides), out))

    def get_overrides(self, handle: int) -> list[int]:
        return self._result_array(lambda out: self._raw_GetOverrides(handle, out))

    def get_master_record(self, handle: int) -> int:
        return self._result_handle(lambda out: self._raw_GetMasterRecord(handle, out))

    def is_master(self, handle: int) -> bool:
        return self._result_bool(lambda out: self._raw_IsMaster(handle, out))
