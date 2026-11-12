param(
    [Parameter(Mandatory=$true)][string]$DllPath,
    [Parameter(Mandatory=$true)][string]$WorkDirectory
)
$ErrorActionPreference = 'Stop'
$WorkDirectory = (Resolve-Path $WorkDirectory).Path
$DllPath = (Resolve-Path $DllPath).Path
$expected = 'A9C41377C6E8F49D911ECA452CC28AD18F33249733AB529AFEA2120FE0AA3B43'
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $DllPath).Hash
if ($hash -ne $expected) { throw 'Wrong DLL build: the extraction offsets apply only to the documented SHA-256.' }
if ([Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString() -ne 'Arm64') {
    throw 'Run this harness in native ARM64 PowerShell on Windows ARM64.'
}
Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Runtime.InteropServices;
public class NativeWmk {
 [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
 public static extern IntPtr LoadLibrary(string path);
 [DllImport("Watermarker.dll", CallingConvention=CallingConvention.Cdecl)]
 public static extern int WmkWriteWatermark(byte[] dst, byte[] msg, ulong len,
     int w, int h, int stride, byte[] src, int fmt);
 public static void ExportTrees(IntPtr module, string path) {
  using (var writer = new BinaryWriter(File.Create(path))) {
   for (int tree=0; tree<12; tree++) for (int vector=0; vector<5; vector++) {
    long address=module.ToInt64()+0x128900+tree*120+vector*24;
    long begin=Marshal.ReadInt64(new IntPtr(address));
    long end=Marshal.ReadInt64(new IntPtr(address+8));
    int count=checked((int)(end-begin));
    if (count<0 || count>4096) throw new Exception("Unexpected model vector length");
    byte[] data=new byte[count]; Marshal.Copy(new IntPtr(begin), data, 0, count);
    writer.Write(count); writer.Write(data);
   }
  }
 }
}
'@
$module = [NativeWmk]::LoadLibrary($DllPath)
if ($module -eq [IntPtr]::Zero) { throw ('LoadLibrary failed: '+[Runtime.InteropServices.Marshal]::GetLastWin32Error()) }
[byte[]]$dct = New-Object byte[] 128
[Runtime.InteropServices.Marshal]::Copy([IntPtr]($module.ToInt64()+0x128880),$dct,0,128)
[IO.File]::WriteAllBytes((Join-Path $WorkDirectory 'dct.bin'),$dct)
[NativeWmk]::ExportTrees($module,(Join-Path $WorkDirectory 'trees.bin'))
$jobs = Get-Content -Raw (Join-Path $WorkDirectory 'jobs.json') | ConvertFrom-Json
$results = @()
foreach ($job in $jobs) {
    $source = [IO.File]::ReadAllBytes((Join-Path $WorkDirectory $job.input))
    if ($source.Length -ne $job.w*$job.h*4) { throw ('Invalid input length: '+$job.name) }
    $message = [Convert]::FromBase64String($job.payload)
    if ($message.Length -ne 16) { throw 'Expected a 16-byte payload' }
    $output = New-Object byte[] $source.Length
    $status = [NativeWmk]::WmkWriteWatermark($output,$message,16,$job.w,$job.h,($job.w*4),$source,1)
    if ($status -eq 0) { [IO.File]::WriteAllBytes((Join-Path $WorkDirectory ($job.name+'.argb')),$output) }
    $results += [PSCustomObject]@{name=$job.name;status=$status;dll_sha256=$hash}
    Write-Output ($job.name+': '+$status)
}
ConvertTo-Json -InputObject @($results) -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $WorkDirectory 'native_results.json')
