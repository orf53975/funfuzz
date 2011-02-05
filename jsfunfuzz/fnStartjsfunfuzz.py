#!/usr/bin/env python
#
#/* ***** BEGIN LICENSE BLOCK	****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is startjsfunfuzz.
#
# The Initial Developer of the Original Code is
# Gary Kwong.
# Portions created by the Initial Developer are Copyright (C) 2008-2010
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.

'''
This file contains functions for startjsfunfuzz.py.
'''

import os, platform, shutil, subprocess, sys, shlex

from multiprocessing import cpu_count

verbose = False  # Turn this to True to enable verbose output for debugging.
showCapturedCommands = False

# This is used for propagating the global repository directory across functions in this file.
globalRepo = ''

def exceptionBadCompileType():
    raise Exception('Unknown compileType')
def exceptionBadBranchType():
    raise Exception('Unknown branchType')
def exceptionBadOs():
    raise Exception("Unknown OS - Platform is unsupported.")

def verboseDump(input):
    '''
    This function appends the word 'DEBUG' to any verbose output.
    '''
    if verbose:
        print 'DEBUG -', input

def osCheck():
    '''
    This function checks for supported operating systems.
    It returns macVer in the case of 10.5.x or 10.6.x.
    '''
    if os.name == 'posix':
        if os.uname()[0] == 'Darwin':
            macVer, _, _ = platform.mac_ver()
            macVer = float('.'.join(macVer.split('.')[:2]))
            if ('10.5' or '10.6' in str(macVer)):
                return str(macVer)
            else:
                exceptionBadOs()  # Only 10.5.x and 10.6.x is supported.
        elif os.uname()[0] == 'Linux':
            pass
    elif os.name == 'nt':
        if float(sys.version[:3]) < 2.6:
            raise Exception('A minimum Python version of 2.6 is required.')
    else:
        print '\nOnly Windows XP/Vista/7, Linux or Mac OS X 10.6.x are supported.\n'
        raise Exception('Unknown OS - Platform is unsupported.')

def error(branchSupp):
    '''
    This function prints the corresponding CLI requirements that should be input.
    '''
    print '\n==========\n| Error! |\n=========='
    print 'General usage: python startjsfunfuzz.py [32|64] [dbg|opt]',
    print '%s [patch <directory to patch>] [patch <directory to patch>]' % branchSupp,
    print '[valgrind]\n'
    print
    print 'Requirements: Python 2.6.x, Mozilla build prerequisites and repositories at "/" (WinXP) or "~/" (other platforms).'
    print
    print 'Windows platforms only compile in 32-bit.'
    print 'Valgrind only works for Linux platforms.\n'

def captureStdout(cmd, ignoreStderr=False, combineStderr=False, ignoreExitCode=False):
    '''
    This function captures standard output into a python string.
    '''
    if showCapturedCommands:
        print ' '.join(cmd)
    p = subprocess.Popen(cmd,
        stdin = subprocess.PIPE,
        stdout = subprocess.PIPE,
        stderr = subprocess.STDOUT if combineStderr else subprocess.PIPE)
    (stdout, stderr) = p.communicate()
    if not ignoreExitCode and p.returncode != 0:
        # Potential problem area: Note that having a non-zero exit code does not mean that the operation
        # did not succeed, for example when compiling a shell. A non-zero exit code can appear even
        # though a shell compiled successfully. This issue has been bypassed in the makeShell
        # function in autoBisect.
        # Pymake in builds earlier than revision 232553f741a0 did not support the '-s' option.
        if 'no such option: -s' not in stdout:
            print 'Nonzero exit code from ' + repr(cmd)
            print stdout
        if stderr is not None:
            print stderr
        # Pymake in builds earlier than revision 232553f741a0 did not support the '-s' option.
        if 'no such option: -s' not in stdout:
            raise Exception('Nonzero exit code')
    if not combineStderr and not ignoreStderr and len(stderr) > 0:
        print 'Unexpected output on stderr from ' + repr(cmd)
        print stdout, stderr
        raise Exception('Unexpected output on stderr')
    if showCapturedCommands:
        print stdout
        if stderr is not None:
            print stderr
    return stdout.rstrip()

def hgHashAddToFuzzPath(fuzzPath):
    '''
    This function finds the mercurial revision and appends it to the directory name.
    It also prompts if the user wants to continue, should the repository not be on tip.
    '''
    verboseDump('About to start running `hg identify -i -n -b` ...')
    hgIdFull = captureStdout(['hg', 'identify', '-i', '-n', '-b'])
    hgIdChangesetHash = hgIdFull.split(' ')[0]
    hgIdLocalNum = hgIdFull.split(' ')[1]
    hgIdBranch = hgIdFull.split(' ')[2]  # If on tip, value should be 'default'.
    onDefaultTip = True
    if hgIdBranch != 'default':
        print 'The repository is at this changeset -', hgIdLocalNum + ':' + hgIdChangesetHash
        notOnDefaultTipApproval = str(raw_input('Not on default tip! Are you sure you want to continue? (y/n): '))
        if notOnDefaultTipApproval == ('y' or 'yes'):
            onDefaultTip = False
        else:
            switchToDefaultTipApproval = str(raw_input('Do you want to switch to the default tip? (y/n): '))
            if switchToDefaultTipApproval == ('y' or 'yes'):
                subprocess.call(['hg', 'up', 'default'])
            else:
                raise Exception('Not on default tip.')
    fuzzPath = fuzzPath[:-1] + '-' + hgIdLocalNum + '-' + hgIdChangesetHash + os.sep
    verboseDump('Finished running `hg identify -i -n -b`.')
    return os.path.normpath(fuzzPath), onDefaultTip

def cpJsTreeDir(repo, dest):
    '''
    This function copies the js tree or the pymake build directory.
    '''
    # This globalRepo variable is only needed to propagate the repository to compileCopy function, it can be
    # removed if compileCopy accepts a repo directory as one of its parameters.
    global globalRepo
    globalRepo = repo
    repo = os.path.normpath(os.path.join(repo, 'js', 'src'))
    if 'Windows-XP' not in platform.platform():
        repo = os.path.expanduser(repo)
    try:
        verboseDump('Copying the js tree, which is located at ' + repo)
        shutil.copytree(os.path.normpath(repo), dest, ignore=shutil.ignore_patterns('tests', 'trace-test', 'xpconnect'))
        verboseDump('Finished copying the js tree')
    except OSError as e:
        if verbose:
            print repr(e)
        raise Exception("Either the js tree directory located at '" + repo + "' doesn't exist, or the destination already exists.")

def autoconfRun(cwd):
    '''
    Sniff platform and run different autoconf types:
    '''
    if os.name == 'posix':
        if os.uname()[0] == 'Darwin':
            subprocess.call(['autoconf213'], cwd=cwd)
        elif os.uname()[0] == 'Linux':
            subprocess.call(['autoconf2.13'], cwd=cwd)
    elif os.name == 'nt':
        subprocess.call(['sh', 'autoconf-2.13'], cwd=cwd)

def cfgJsBin(archNum, compileType, traceJit, methodJit,
                      valgrindSupport, threadsafe, macver, configure, objdir):
    '''
    This function configures a js binary depending on the parameters.
    '''
    cfgCmd = 'sh ' + os.path.normpath(configure)
    if (archNum == '32') and (os.name == 'posix'):
        if os.uname()[0] == "Darwin":
            if macver == '10.6':
                cfgCmd = 'CC="gcc-4.2 -arch i386" CXX="g++-4.2 -arch i386" ' + \
                             'HOST_CC="gcc-4.2" HOST_CXX="g++-4.2" ' + \
                             'RANLIB=ranlib AR=ar AS=$CC LD=ld ' + \
                             'STRIP="strip -x -S" CROSS_COMPILE=1 ' + \
                             'sh ' + configure + ' --target=i386-apple-darwin8.0.0'
        elif (os.uname()[0] == "Linux") and (os.uname()[4] != 'armv7l'):
            # apt-get `ia32-libs gcc-multilib g++-multilib` first, if on 64-bit Linux.
            cfgCmd = 'CC="gcc -m32" CXX="g++ -m32" AR=ar sh ' + configure + ' --target=i686-pc-linux'
        elif os.uname()[4] == 'armv7l':
            if os.uname()[1] == 'tegra-ubuntu':
                # No special commands needed, but be sure to install Linux prerequisites,
                # do not worry if build-dep does not work, also be sure to apt-get zip as well.
                pass
                #cfgCmd = 'CC=/opt/cs2007q3/bin/gcc CXX=/opt/cs2007q3/bin/g++ ' + \
                             #'sh ' + configure
                # The binary below is an x86 binary rather than an ARM one.
                #cfgCmd = 'CC=/opt/3rdparty/arm-2009q1/bin/arm-none-linux-gnueabi-gcc ' + \
                             #'CXX=/opt/3rdparty/arm-2009q1/bin/arm-none-linux-gnueabi-g++ ' + \
                             #'sh ' + configure
            else:
                cfgCmd = 'CC=/opt/cs2007q3/bin/gcc CXX=/opt/cs2007q3/bin/g++ ' + \
                             'sh ' + configure
    if (archNum == '64') and (macver == '10.5'):
        cfgCmd = 'CC="gcc -m64" CXX="g++ -m64" AR=ar ' + \
                     'sh ' + configure + ' --target=x86_64-apple-darwin10.0.0'

    if compileType == 'dbg':
        cfgCmd += ' --disable-tests --disable-optimize --enable-debug'
    elif compileType == 'opt':
        # --enable-profiling is needed to obtain backtraces on optimized shells.
        cfgCmd += ' --disable-tests --enable-optimize --disable-debug --enable-profiling'

    # Trace JIT is on by default.
    if not traceJit:
        cfgCmd += ' --disable-tracejit'
    # Method JIT is off by default.
    if methodJit:
        cfgCmd += ' --enable-methodjit'
    if valgrindSupport:
        cfgCmd += ' --enable-valgrind'
    if threadsafe:
        cfgCmd += ' --enable-threadsafe --with-system-nspr'

    cfgCmd += ' --enable-type-inference'

    if os.name == 'nt':
        # Only tested to work for pymake.
        cfgCmd = cfgCmd.replace(os.sep, '\\\\')

    verboseDump('This is the configure command:')
    verboseDump('%s\n' % cfgCmd)
    
    if os.name == 'nt':
        nullLocation = open('nul', 'w')
    else:
        nullLocation = open('/dev/null', 'w')
    
    args = shlex.split(cfgCmd)
    verboseDump(args)
    
    # If on Windows, be sure to first install prerequisites at https://developer.mozilla.org/En/Windows_SDK_versions
    # Note that on Windows, redirecting stdout to subprocess.STDOUT does not work on Python 2.6.5.
    subprocess.call(args, stdout=nullLocation, stderr=subprocess.STDOUT, cwd=objdir)
        
def binaryPostfix():
    if os.name == 'posix':
        return ''
    elif os.name == 'nt':
        return '.exe'

def shellName(archNum, compileType, extraID):
    if os.name == 'posix':
        osname = os.uname()[0].lower()
    elif os.name == 'nt':
        osname = os.name.lower()
    return 'js-' + compileType + '-' + archNum + '-' + extraID + '-' + osname + binaryPostfix()

def compileCopy(archNum, compileType, extraID, usePymake, destDir, objdir):
    '''
    This function compiles and copies a binary.
    '''
    jobs = (cpu_count() * 3) // 2
    compiledName = os.path.join(objdir, 'js' + binaryPostfix())
    try:
        if usePymake:
            out = captureStdout(['python', '-O', os.path.normpath(os.path.join(globalRepo, 'build', 'pymake', 'make.py')), '-j' + str(jobs), '-s'], combineStderr=True)
            # Pymake in builds earlier than revision 232553f741a0 did not support the '-s' option.
            if 'no such option: -s' in out:
                out = captureStdout(['python', '-O', os.path.normpath(os.path.join(globalRepo, 'build', 'pymake', 'make.py')), '-j' + str(jobs)], combineStderr=True)
        else:
            out = captureStdout(['make', '-C', objdir, '-j' + str(jobs), '-s'], combineStderr=True, ignoreExitCode=True)
    except:
        # Sometimes a non-zero error can be returned during the make process, but eventually a
        # shell still gets compiled.
        if os.path.exists(compiledName):
            print 'A shell was compiled even though there was a non-zero exit code returned. Continuing...'
        else:
            if verbose:
                print out
            raise Exception("Running 'make' did not result in a js shell")

    newName = os.path.join(destDir, shellName(archNum, compileType, extraID))
    shutil.copy2(compiledName, newName)
    return newName

def cpUsefulFiles(filePath):
    '''
    This function copies over useful files that are updated in hg fuzzing branch.
    '''
    if 'Windows-XP' not in platform.platform():
        filePath = os.path.expanduser(filePath)
    shutil.copy2(filePath, '.')

def archOfBinary(b):
    '''
    This function tests if a binary is 32-bit or 64-bit.
    '''
    filetype = captureStdout(['file', b])
    if 'universal binary' in filetype:
        raise Exception("I don't know how to deal with multiple-architecture binaries")
    if '386' in filetype or '32-bit' in filetype:
        return '32'
    if '64-bit' in filetype:
        return '64'

def grabExitCodeAfterTestingDbgOrOpt(jsShell):
    '''
    This function grabs the error code after testing the shell, whether it is debug or opt.
    '''
    # Create a testfile with the gczeal() function.
    compileTypeTestName = 'compileTypeTest.js'
    compileTypeTestFile = open(compileTypeTestName, 'w')
    compileTypeTestFile.writelines('gczeal()')
    compileTypeTestFile.close()
    # Test that compileTypeTestFile is indeed created.
    if not os.path.isfile(compileTypeTestName):
        raise Exception(compileTypeTestName, 'does not exist.')

    if os.name == 'posix':
        testFileErrNum = subprocess.call([jsShell, compileTypeTestName])
    elif os.name == 'nt':
        testFileErrNum = subprocess.call([jsShell, compileTypeTestName], shell=True)
    os.remove(compileTypeTestName)  # Remove testfile after grabbing the error code.
    
    return testFileErrNum

def testDbgOrOpt(jsShellName):
    '''
    This function tests if a binary is a debug or optimized shell.
    '''
    exitCode = grabExitCodeAfterTestingDbgOrOpt(jsShellName)
    
    # The error code for debug shells when passing in the gczeal() function should be 0.
    if exitCode == 0:
        return 'dbg'
    # Optimized shells don't have gczeal() compiled in by default.
    elif exitCode == 3:
        return 'opt'
    else:
        raise Exception('Unknown exit code after testing if debug or opt: ' + exitCode)

def testDbgOrOptGivenACompileType(jsShellName, compileType):
    '''
    This function tests if a binary is a debug or optimized shell given a compileType.
    '''
    exitCode = grabExitCodeAfterTestingDbgOrOpt(jsShellName)

    verboseDump('The error code for debug shells should be 0.')
    verboseDump('The error code for opt shells should be 3.')
    verboseDump('The actual error code for ' + jsShellName + ' now, is: ' + str(exitCode))

    # The error code for debug shells when passing in the gczeal() function should be 0.
    if compileType == 'dbg' and exitCode != 0:
        print 'ERROR: A debug shell when tested with the gczeal() should return "0" as the error code.'
        print 'compileType is: ' + compileType
        print 'exitCode is: ' + str(exitCode)
        print
        raise Exception('The compiled binary is not a debug shell.')
    # Optimized shells don't have gczeal() compiled in by default.
    elif compileType == 'opt' and exitCode != 3:
        print 'ERROR: An optimized shell when tested with the gczeal() should return "3" as the error code.'
        print 'compileType is: ' + compileType
        print 'exitCode is: ' + str(exitCode)
        print
        raise Exception('The compiled binary is not an optimized shell.')

if __name__ == '__main__':
    pass
