// Prints upcoming Calendar events as JSON: dock-calendar [days]
// Uses EventKit so recurring events are expanded correctly.
import EventKit
import Foundation

let days = Int(CommandLine.arguments.dropFirst().first ?? "2") ?? 2
let store = EKEventStore()
let sem = DispatchSemaphore(value: 0)
var granted = false

if #available(macOS 14.0, *) {
    store.requestFullAccessToEvents { ok, _ in granted = ok; sem.signal() }
} else {
    store.requestAccess(to: .event) { ok, _ in granted = ok; sem.signal() }
}
_ = sem.wait(timeout: .now() + 20)

func out(_ obj: Any) {
    let data = try! JSONSerialization.data(withJSONObject: obj, options: [])
    FileHandle.standardOutput.write(data)
}

if !granted {
    out(["ok": false, "error": "no_access"])
    exit(0)
}

let cal = Calendar.current
let start = cal.startOfDay(for: Date())
let end = cal.date(byAdding: .day, value: days, to: start)!
let pred = store.predicateForEvents(withStart: start, end: end, calendars: nil)
let iso = ISO8601DateFormatter()
iso.formatOptions = [.withInternetDateTime]
var events: [[String: Any]] = []
for e in store.events(matching: pred).sorted(by: { $0.startDate < $1.startDate }) {
    var c = "#8e8e93"
    if let cg = e.calendar.cgColor, let comps = cg.components, comps.count >= 3 {
        c = String(format: "#%02x%02x%02x", Int(comps[0] * 255), Int(comps[1] * 255), Int(comps[2] * 255))
    }
    events.append([
        "title": e.title ?? "",
        "start": iso.string(from: e.startDate),
        "end": iso.string(from: e.endDate),
        "allDay": e.isAllDay,
        "calendar": e.calendar.title,
        "color": c,
        "location": e.location ?? "",
    ])
}
out(["ok": true, "events": events])
