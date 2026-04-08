{ pkgs }: {
  deps = [
    pkgs.python311
    pkgs.ffmpeg
    pkgs.libsodium
    pkgs.libopus
  ];
}
