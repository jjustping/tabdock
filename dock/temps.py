"""Apple Silicon temperature sensors via IOHIDEventSystem (no sudo).

Uses the same private-but-stable IOKit HID API that tools like Stats use.
Returns {} on any failure so the dock keeps working on unknown hardware.
"""
import ctypes
import threading

_lock = threading.Lock()
_cf = _iokit = None
_ok = None

kCFStringEncodingUTF8 = 0x08000100
kCFNumberSInt32Type = 3
kIOHIDEventTypeTemperature = 15


def _init():
    global _cf, _iokit, _ok
    if _ok is not None:
        return _ok
    try:
        cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        io = ctypes.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")
        vp = ctypes.c_void_p
        cf.CFStringCreateWithCString.restype = vp
        cf.CFStringCreateWithCString.argtypes = [vp, ctypes.c_char_p, ctypes.c_uint32]
        cf.CFNumberCreate.restype = vp
        cf.CFNumberCreate.argtypes = [vp, ctypes.c_int, vp]
        cf.CFDictionaryCreate.restype = vp
        cf.CFDictionaryCreate.argtypes = [vp, vp, vp, ctypes.c_long, vp, vp]
        cf.CFArrayGetCount.restype = ctypes.c_long
        cf.CFArrayGetCount.argtypes = [vp]
        cf.CFArrayGetValueAtIndex.restype = vp
        cf.CFArrayGetValueAtIndex.argtypes = [vp, ctypes.c_long]
        cf.CFStringGetCString.restype = ctypes.c_bool
        cf.CFStringGetCString.argtypes = [vp, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
        cf.CFRelease.argtypes = [vp]
        io.IOHIDEventSystemClientCreate.restype = vp
        io.IOHIDEventSystemClientCreate.argtypes = [vp]
        io.IOHIDEventSystemClientSetMatching.argtypes = [vp, vp]
        io.IOHIDEventSystemClientCopyServices.restype = vp
        io.IOHIDEventSystemClientCopyServices.argtypes = [vp]
        io.IOHIDServiceClientCopyProperty.restype = vp
        io.IOHIDServiceClientCopyProperty.argtypes = [vp, vp]
        io.IOHIDServiceClientCopyEvent.restype = vp
        io.IOHIDServiceClientCopyEvent.argtypes = [vp, ctypes.c_int64, ctypes.c_int32, ctypes.c_int64]
        io.IOHIDEventGetFloatValue.restype = ctypes.c_double
        io.IOHIDEventGetFloatValue.argtypes = [vp, ctypes.c_int32]
        _cf, _iokit = cf, io
        _ok = True
    except Exception:
        _ok = False
    return _ok


def _cfstr(s):
    return _cf.CFStringCreateWithCString(None, s.encode(), kCFStringEncodingUTF8)


def _cfnum(n):
    v = ctypes.c_int32(n)
    return _cf.CFNumberCreate(None, kCFNumberSInt32Type, ctypes.byref(v))


def _pystr(ref):
    if not ref:
        return ""
    buf = ctypes.create_string_buffer(256)
    if _cf.CFStringGetCString(ref, buf, 256, kCFStringEncodingUTF8):
        return buf.value.decode(errors="replace")
    return ""


def read_sensors():
    """Return {sensor_name: celsius}."""
    with _lock:
        if not _init():
            return {}
        cf, io = _cf, _iokit
        try:
            keys = (ctypes.c_void_p * 2)(_cfstr("PrimaryUsagePage"), _cfstr("PrimaryUsage"))
            vals = (ctypes.c_void_p * 2)(_cfnum(0xFF00), _cfnum(5))
            kcb = ctypes.addressof(ctypes.c_void_p.in_dll(cf, "kCFTypeDictionaryKeyCallBacks"))
            vcb = ctypes.addressof(ctypes.c_void_p.in_dll(cf, "kCFTypeDictionaryValueCallBacks"))
            match = cf.CFDictionaryCreate(None, keys, vals, 2, kcb, vcb)
            client = io.IOHIDEventSystemClientCreate(None)
            io.IOHIDEventSystemClientSetMatching(client, match)
            services = io.IOHIDEventSystemClientCopyServices(client)
            out = {}
            if services:
                prod_key = _cfstr("Product")
                for i in range(cf.CFArrayGetCount(services)):
                    svc = cf.CFArrayGetValueAtIndex(services, i)
                    name_ref = io.IOHIDServiceClientCopyProperty(svc, prod_key)
                    name = _pystr(name_ref)
                    if name_ref:
                        cf.CFRelease(name_ref)
                    ev = io.IOHIDServiceClientCopyEvent(svc, kIOHIDEventTypeTemperature, 0, 0)
                    if ev:
                        t = io.IOHIDEventGetFloatValue(ev, kIOHIDEventTypeTemperature << 16)
                        cf.CFRelease(ev)
                        if name and 0 < t < 150:
                            out[name] = round(t, 1)
                cf.CFRelease(prod_key)
                cf.CFRelease(services)
            cf.CFRelease(client)
            cf.CFRelease(match)
            for r in list(keys) + list(vals):
                cf.CFRelease(r)
            return out
        except Exception:
            return {}


def summary():
    """CPU (SoC die) and SSD temperature summary for the dashboard."""
    s = read_sensors()
    if not s:
        return {"cpu": None, "ssd": None, "sensors": 0}
    die = [v for k, v in s.items() if "tdie" in k.lower() or "acc mtr" in k.lower() or "soc mtr" in k.lower()]
    if not die:
        die = [v for k, v in s.items() if k.startswith("PMU") and "tcal" not in k.lower()]
    nand = [v for k, v in s.items() if "nand" in k.lower()]
    return {
        "cpu": round(max(die), 1) if die else None,
        "cpu_avg": round(sum(die) / len(die), 1) if die else None,
        "ssd": round(max(nand), 1) if nand else None,
        "sensors": len(s),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(read_sensors(), indent=1, ensure_ascii=False))
    print(summary())
