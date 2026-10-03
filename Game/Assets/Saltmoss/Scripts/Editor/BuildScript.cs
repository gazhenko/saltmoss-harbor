using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace Saltmoss.EditorTools
{
    /// <summary>Batch builds: -executeMethod Saltmoss.EditorTools.BuildScript.BuildAll [-platforms mac,win,linux] [-out ../Builds] [-dev]</summary>
    public static class BuildScript
    {
        public const string MacApp = "Saltmoss Harbor.app", WinExe = "SaltmossHarbor.exe", LinuxBin = "SaltmossHarbor.x86_64";

        [MenuItem("Saltmoss/Build/All Platforms")]
        public static void BuildAll()
        {
            string plats = CommandLine.Get("-platforms", "mac,win,linux");
            string outDir = CommandLine.Get("-out", Path.GetFullPath(Path.Combine(Application.dataPath, "../../Builds")));
            bool dev = CommandLine.Has("-dev");
            bool ok = true;
            foreach (var p in plats.Split(','))
            {
                switch (p.Trim())
                {
                    case "mac": ok &= Build(BuildTarget.StandaloneOSX, Path.Combine(outDir, "mac", MacApp), dev); break;
                    case "win": ok &= Build(BuildTarget.StandaloneWindows64, Path.Combine(outDir, "win", WinExe), dev); break;
                    case "linux": ok &= Build(BuildTarget.StandaloneLinux64, Path.Combine(outDir, "linux", LinuxBin), dev); break;
                }
            }
            if (Application.isBatchMode) EditorApplication.Exit(ok ? 0 : 1);
        }

        static bool Build(BuildTarget target, string path, bool dev)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            var scenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToArray();
            if (scenes.Length == 0) { Debug.LogError("[Build] No scenes in build settings"); return false; }
#if UNITY_EDITOR_OSX
            if (target == BuildTarget.StandaloneOSX)
                UnityEditor.OSXStandalone.UserBuildSettings.architecture = UnityEditor.Build.OSArchitecture.x64ARM64;
#endif
            var opts = new BuildPlayerOptions
            {
                scenes = scenes,
                locationPathName = path,
                target = target,
                targetGroup = BuildTargetGroup.Standalone,
                options = dev ? BuildOptions.Development : BuildOptions.None,
            };
            var report = BuildPipeline.BuildPlayer(opts);
            var s = report.summary;
            Debug.Log($"[Build] {target}: {s.result} {s.totalSize / (1024 * 1024)} MB in {s.totalTime.TotalSeconds:0}s errors={s.totalErrors} -> {path}");
            return s.result == BuildResult.Succeeded;
        }
    }
}
