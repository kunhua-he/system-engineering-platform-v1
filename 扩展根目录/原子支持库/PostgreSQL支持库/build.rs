use std::process::Command;
fn main() {
    let 配置程序 = std::env::var_os("PG_CONFIG").unwrap_or_else(|| "pg_config".into());
    let 配置回执 = Command::new(配置程序)
        .arg("--libdir")
        .output()
        .expect("pg_config required");
    assert!(配置回执.status.success(), "pg_config failed");
    let 引擎目录 = String::from_utf8(配置回执.stdout).expect("libdir UTF-8");
    println!("cargo:rustc-link-search=native={}", 引擎目录.trim());
    println!("cargo:rustc-link-lib=dylib=pq");
    println!("cargo:rerun-if-env-changed=PG_CONFIG");
}
