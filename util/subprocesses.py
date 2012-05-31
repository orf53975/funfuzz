#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import with_statement

import os
import platform
import re
import subprocess
import time

verbose = False

########################
#  Platform Detection  #
########################

def macType():
    '''
    If system is a Mac, return the mac type.
    '''
    assert platform.system() in ('Windows', 'Linux', 'Darwin')
    isMac = isSL = amiLion = False
    if platform.system() == 'Darwin':
        isMac = True
        # Script has only been tested on Snow Leopard and Lion.
        assert 6 <= int(platform.mac_ver()[0].split('.')[1]) <= 7
        isSL = isMac and platform.mac_ver()[0].split('.')[1] == '6' \
            and platform.mac_ver()[0].split('.') >= ['10', '6']
        amiLion = isMac and platform.mac_ver()[0].split('.')[1] == '7' \
            and platform.mac_ver()[0].split('.') >= ['10', '7']
    return (isMac, isSL, amiLion)

def isVM():
    '''
    Returns the OS of the system, if system is a VM.
    '''
    vm = False
    # In VMware, shared folders are in z:, and we copy from the shared folders to avoid having
    # another copy of the repository in the VM.
    if (platform.uname()[2] == 'XP' \
            and os.path.exists(os.path.join('z:', os.sep, 'fuzzing'))) or \
        platform.uname()[0] == 'Linux' \
            and os.path.exists(os.path.join('/', 'mnt', 'hgfs', 'fuzzing')):
        assert not os.path.exists(normExpUserPath(os.path.join('~', 'fuzzing')))
        assert not os.path.exists(normExpUserPath(os.path.join('~', 'trees')))
        vm = True
    return (platform.system(), vm)

#####################
#  Shell Functions  #
#####################

def captureStdout(inputCmd, ignoreStderr=False, combineStderr=False, ignoreExitCode=False,
                  currWorkingDir=os.getcwdu(), env=os.environ, verbosity=False):
    '''
    Captures standard output, returns the output as a string, along with the return value.
    '''
    vdump(shellify(inputCmd))
    cmd = []
    for el in inputCmd:
        if (el.startswith('"') and el.endswith('"')):
            cmd.append(str(el[1:-1]))
        else:
            cmd.append(str(el))
    assert cmd != []
    p = subprocess.Popen(cmd,
        stdin = subprocess.PIPE,
        stdout = subprocess.PIPE,
        stderr = subprocess.STDOUT if combineStderr else subprocess.PIPE,
        cwd=currWorkingDir, env=env)
    (stdout, stderr) = p.communicate()
    if not ignoreExitCode and p.returncode != 0:
        # Potential problem area: Note that having a non-zero exit code does not mean that the
        # operation did not succeed, for example when compiling a shell. A non-zero exit code can
        # appear even though a shell compiled successfully. This issue has been bypassed in the
        # makeShell function in autoBisect.
        # Pymake in builds earlier than revision 232553f741a0 did not support the '-s' option.
        if 'no such option: -s' not in stdout:
            print 'Nonzero exit code from: '
            print '  ' + shellify(cmd)
            print stdout
        if stderr is not None:
            print stderr
        # Pymake in builds earlier than revision 232553f741a0 did not support the '-s' option.
        if 'hg pull: option --rebase not recognized' not in stdout and \
          'no such option: -s' not in stdout:
            raise Exception('Nonzero exit code')
    if not combineStderr and not ignoreStderr and len(stderr) > 0:
        if not ((platform.system() == 'Windows' and \
            # Ignore hg color mode throwing an error in console on Windows platforms.
            'warning: failed to set color mode to win32' in stderr) or \
            (isVM() == ('Linux', True) and \
            # Ignore stderr warning when running a Linux VM on a Mac host:
            # Not trusting file /mnt/hgfs/trees/mozilla-central/.hg/hgrc from untrusted user 501...
            'hgrc from untrusted user 501' in stderr)):
            print 'Unexpected output on stderr from: '
            print '  ' + shellify(cmd)
            print stdout, stderr
            raise Exception('Unexpected output on stderr')
    if stderr and ignoreStderr and len(stderr) > 0 and p.returncode != 0:
        # During configure, there will always be stderr. Sometimes this stderr causes configure to
        # stop the entire script, especially on Windows.
        print 'Return code not zero, and unexpected output on stderr from: '
        print '  ' + shellify(cmd)
        print stdout, stderr
        raise Exception('Return code not zero, and unexpected output on stderr')
    if verbose or verbosity:
        print stdout
        if stderr is not None:
            print stderr
    return stdout.rstrip(), p.returncode

def dateStr():
    '''
    Equivalent of: assert subprocess.check_output(['Date'])[:-1] == currDateTime
    '''
    currTz = time.tzname[0] if time.daylight == 1 else time.tzname[1]
    currAscDateTime = time.asctime( time.localtime(time.time()) )
    currDateTime = currAscDateTime[:-4] + currTz + ' ' + currAscDateTime[-4:]
    return currDateTime

def grabMacCrashLog(progname, crashedPID, logPrefix, useLogFiles):
    '''Finds the required crash log in the given crash reporter directory.'''
    assert platform.system() == 'Darwin'
    isLeopard = platform.mac_ver()[0].startswith("10.5")
    reportDirList = [os.path.expanduser('~'), '/']
    for baseDir in reportDirList:
        # Sometimes the crash reports end up in the root directory.
        # This possibly happens when the value of <value>:
        #     defaults write com.apple.CrashReporter DialogType <value>
        # is none, instead of server, or some other option.
        # See http://en.wikipedia.org/wiki/Crash_Reporter_%28Mac_OS_X%29
        reportDir = os.path.join(baseDir, 'Library/Logs/CrashReporter/') if isLeopard \
            else os.path.join(baseDir, 'Library/Logs/DiagnosticReports/')
        # Find a crash log for the right process name and pid, preferring
        # newer crash logs (which sort last).
        try:
            crashLogs = os.listdir(reportDir)
        except (OSError, IOError), e:
            # Maybe this is the first crash ever on this computer, and the dir does not yet exist.
            crashLogs = []
        # Firefox sometimes still runs as firefox-bin, at least on Mac (likely bug 658850)
        crashLogs = filter(
            lambda s: (s.startswith(progname + "_") or s.startswith(progname + "-bin_")), crashLogs)
        crashLogs.sort(reverse=True)
        for fn in crashLogs:
            fullfn = os.path.join(reportDir, fn)
            try:
                with open(fullfn) as c:
                    firstLine = c.readline()
                if firstLine.rstrip().endswith("[" + str(crashedPID) + "]"):
                    if useLogFiles:
                        os.rename(fullfn, logPrefix + "-crash")
                        return logPrefix + "-crash"
                    else:
                        return fullfn
                        #return open(fullfn).read()

            except (OSError, IOError), e:
                # Maybe the log was rotated out between when we got the list
                # of files and when we tried to open this file.  If so, it's
                # clearly not The One.
                pass
    return None

def grabCrashLog(progname, progfullname, crashedPID, logPrefix):
    '''Returns the crash log if found.'''
    if progname == "valgrind":
        return
    useLogFiles = isinstance(logPrefix, str)
    if useLogFiles:
        if os.path.exists(logPrefix + "-crash"):
            os.remove(logPrefix + "-crash")
        if os.path.exists(logPrefix + "-core"):
            os.remove(logPrefix + "-core")

    # On Mac and Linux, look for a core file.
    coreFilename = None
    if platform.system() == "Darwin":
        # Assuming you ran: mkdir -p /cores/
        coreFilename = "/cores/core." + str(crashedPID)
    elif platform.system() == "Linux":
        isPidUsed = False
        if os.path.exists('/proc/sys/kernel/core_uses_pid'):
            with open('/proc/sys/kernel/core_uses_pid') as f:
                isPidUsed = bool(int(f.read()[0]))  # Setting [0] turns the input to a str.
        coreFilename = 'core.' + str(crashedPID) if isPidUsed else 'core'
    if coreFilename and os.path.exists(coreFilename):
        # Run gdb and move the core file. Tip: gdb gives more info for:
        # (debug with intact build dir > debug > opt with frame pointers > opt)
        gdbCommandFile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gdb-quick.txt")
        assert os.path.exists(gdbCommandFile)
        gdbArgs = ["gdb", "-n", "-batch", "-x", gdbCommandFile, progfullname, coreFilename]
        print " ".join(gdbArgs)
        child = subprocess.call(
            gdbArgs,
            stdin =  None,
            stderr = subprocess.STDOUT,
            stdout = open(logPrefix + "-crash", 'w') if useLogFiles else None,
            close_fds = close_fds
        )
        if useLogFiles:
            os.rename(coreFilename, logPrefix + "-core")
            subprocess.call(["gzip", logPrefix + "-core"])
            return logPrefix + "-crash"
        else:
            print "I don't know what to do with a core file when logPrefix is null"

    # On Mac, look for a crash log generated by Mac OS X Crash Reporter
    if platform.system() == "Darwin":
        loops = 0
        maxLoops = 500 if progname.startswith("firefox") else 30
        while True:
            cLogFound = grabMacCrashLog(progname, crashedPID, logPrefix, useLogFiles)
            if cLogFound is not None:
                return cLogFound

            # print "[grabCrashLog] Waiting for the crash log to appear..."
            time.sleep(0.200)
            loops += 1
            if loops > maxLoops:
                # I suppose this might happen if the process corrupts itself so much that
                # the crash reporter gets confused about the process name, for example.
                print "grabCrashLog waited a long time, but a crash log for " + progname + \
                    " [" + str(crashedPID) + "] never appeared!"
                break

def normExpUserPath(p):
    return os.path.normpath(os.path.expanduser(p))

def timeSubprocess(command, ignoreStderr=False, combineStderr=False, ignoreExitCode=False,
                   cwd=os.getcwdu(), env=os.environ, vb=False):
    '''
    Calculates how long a captureStdout command takes and prints it. Returns the stdout and return
    value that captureStdout passes on.
    '''
    print 'Running `%s` now..' % shellify(command)
    startTime = time.time()
    stdOutput, retVal = captureStdout(command, ignoreStderr=ignoreStderr,
                                      combineStderr=combineStderr, ignoreExitCode=ignoreExitCode,
                                      currWorkingDir=cwd, env=env, verbosity=vb)
    endTime = time.time()
    print '`' + shellify(command) + '` took %.3f seconds.\n' % (endTime - startTime)
    return stdOutput, retVal

def shellify(cmd):
    """Try to convert an arguments array to an equivalent string that can be pasted into a shell."""
    okUnquotedRE = re.compile("""^[a-zA-Z0-9\-\_\.\,\/\=\~@]*$""")
    okQuotedRE =   re.compile("""^[a-zA-Z0-9\-\_\.\,\/\=\~@\(\) ]*$""")
    ssc = []
    for i in xrange(len(cmd)):
        item = cmd[i]
        if okUnquotedRE.match(item):
            ssc.append(item)
        elif okQuotedRE.match(item):
            ssc.append('"' + item + '"')
        else:
            vdump("Sorry, shellify doesn't know how to escape " + item)
            return repr(cmd)
    return ' '.join(ssc)

def vdump(inp):
    '''
    This function appends the word 'DEBUG' to any verbose output.
    '''
    if verbose:
        print 'DEBUG -', inp

def createWtmpDir(tmpDirBase):
    '''Create wtmp<number> directory, incrementing the number if one is already found.'''
    i = 1
    while True:
        tmpDirWithNum = 'wtmp' + str(i)
        tmpDir = os.path.join(tmpDirBase, tmpDirWithNum)
        try:
            os.mkdir(tmpDir)  # To avoid race conditions, we use try/except instead of exists/create
            break
        except OSError, e:
            i += 1
    vdump(tmpDirWithNum + os.sep)  # Even if not verbose, wtmp<num> is also dumped: wtmp1/w1: NORMAL
    return tmpDirWithNum

if __name__ == '__main__':
    pass
