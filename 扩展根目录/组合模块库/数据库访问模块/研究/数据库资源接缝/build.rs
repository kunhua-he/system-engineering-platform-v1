use std::process::Command;

fn main() {
    let 配置命令 = std::env::var_os("PG_CONFIG").unwrap_or_else(|| "pg_config".into());
    let 库目录 = Command::new(配置命令)
        .arg("--libdir")
        .output()
        .ok()
        .filter(|回执| 回执.status.success())
        .map(|回执| String::from_utf8_lossy(&回执.stdout).trim().to_owned());
    if let Some(库目录) = 库目录.filter(|路径| !路径.is_empty()) {
        println!("cargo:rustc-link-search=native={库目录}");
    } else {
        for 目录 in [
            "/opt/homebrew/opt/postgresql@18/lib/postgresql",
            "/opt/homebrew/lib/postgresql@18",
            "/usr/local/lib/postgresql",
        ] {
            if std::path::Path::new(目录).exists() {
                println!("cargo:rustc-link-search=native={目录}");
                break;
            }
        }
    }
    println!("cargo:rustc-link-lib=dylib=pq");
    println!("cargo:rerun-if-env-changed=PG_CONFIG");
}
