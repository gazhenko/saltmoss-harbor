#!/usr/bin/env bash
# Fast C# type-check of Game/Assets/Saltmoss/Scripts on the build VM with Unity's bundled Roslyn — no Unity editor,
# no licence, a few seconds. Uses the reference lists from the project's last Unity compile (Library/Bee *.rsp).
#   Tools/cscheck.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${SM_HOST:-kiki-unity}"
RDIR="Projects/saltmoss-harbor/Game"
CDIR="Projects/saltmoss-cscheck"
ssh "$HOST" "mkdir -p $CDIR"
rsync -az --delete --include '*/' --include '*.cs' --exclude '*' "$ROOT/Game/Assets/Saltmoss/Scripts/" "$HOST:$CDIR/Scripts/"
ssh "$HOST" bash -s <<EOF
set -e
U=\$HOME/Unity/6000.3.20f1/Editor/Data
cd \$HOME/$RDIR
RT=\$(ls -t Library/Bee/artifacts/*/Assembly-CSharp.rsp | head -1)
ED=\$(ls -t Library/Bee/artifacts/*/Assembly-CSharp-Editor.rsp | head -1)
C=\$HOME/$CDIR
grep -v -E '\.cs"?$|^-out:|^-refout:|^-warnaserror|^-nowarn' "\$RT" > \$C/rt.rsp
echo "-out:\$C/rt.dll" >> \$C/rt.rsp
echo "-nowarn:0414,0649,0169,0219,0168,0618" >> \$C/rt.rsp
find \$C/Scripts/Runtime -name '*.cs' | sed 's/.*/"&"/' >> \$C/rt.rsp
grep -v -E '\.cs"?$|^-out:|^-refout:|Assembly-CSharp\.(ref\.)?dll|^-warnaserror|^-nowarn' "\$ED" > \$C/ed.rsp
echo "-r:\$C/rt.dll" >> \$C/ed.rsp
echo "-out:\$C/ed.dll" >> \$C/ed.rsp
echo "-nowarn:0414,0649,0169,0219,0168,0618" >> \$C/ed.rsp
find \$C/Scripts/Editor -name '*.cs' | sed 's/.*/"&"/' >> \$C/ed.rsp
echo "== runtime"
\$U/NetCoreRuntime/dotnet exec \$U/DotNetSdkRoslyn/csc.dll /noconfig @\$C/rt.rsp 2>&1 | grep -E "error|warning CS0(1|4)" | sed "s#\$C/##" | head -60 || true
echo "== editor"
\$U/NetCoreRuntime/dotnet exec \$U/DotNetSdkRoslyn/csc.dll /noconfig @\$C/ed.rsp 2>&1 | grep -E "error" | sed "s#\$C/##" | head -60 || true
EOF
