// TabDock.app — tiny launcher so macOS privacy permissions (Full Disk Access, removable volumes,
// Calendar) are granted to "TabDock" instead of an anonymous Python. It starts the server as a
// child process and stays its parent: macOS attributes the child's file access to this app.
//   TabDock.app/Contents/MacOS/TabDock <python> <server.py> [args...]
import Foundation

let args = Array(CommandLine.arguments.dropFirst())
guard args.count >= 2 else {
    FileHandle.standardError.write("usage: TabDock <python> <server.py> [args]\n".data(using: .utf8)!)
    exit(2)
}
var pid: pid_t = 0
var cargs: [UnsafeMutablePointer<CChar>?] = args.map { strdup($0) } + [nil]
let rc = posix_spawn(&pid, args[0], nil, nil, &cargs, environ)
if rc != 0 {
    FileHandle.standardError.write("TabDock: cannot start \(args[0]): \(String(cString: strerror(rc)))\n".data(using: .utf8)!)
    exit(1)
}
// forward stop signals from launchd to the server
for sig in [SIGTERM, SIGINT, SIGHUP] {
    signal(sig, SIG_IGN)
    let src = DispatchSource.makeSignalSource(signal: sig, queue: .main)
    src.setEventHandler { kill(pid, sig) }
    src.resume()
    _ = Unmanaged.passRetained(src as AnyObject)
}
DispatchQueue.global().async {
    var status: Int32 = 0
    waitpid(pid, &status, 0)
    let code = (status & 0x7f) == 0 ? (status >> 8) & 0xff : 1
    exit(code)
}
dispatchMain()
