use std::{env, fs, path::Path};
fn visit(folder: &Path, base: &Path, generated: &mut String) {
    for entry in fs::read_dir(folder).expect("Build the Vite assets before the player") {
        let path = entry.unwrap().path();
        if path.is_dir() {
            visit(&path, base, generated);
        } else {
            let key = path
                .strip_prefix(base)
                .unwrap()
                .to_string_lossy()
                .replace('\\', "/");
            let mime = match path.extension().and_then(|x| x.to_str()).unwrap_or("") {
                "html" => "text/html",
                "js" => "text/javascript",
                "css" => "text/css",
                "svg" => "image/svg+xml",
                _ => "application/octet-stream",
            };
            generated.push_str(&format!(
                "({:?}, {:?}, include_bytes!({:?})),\n",
                format!("/{key}"),
                mime,
                path.canonicalize().unwrap()
            ));
        }
    }
}
fn main() {
    let dist = Path::new("../../dist");
    println!("cargo:rerun-if-changed=../../dist");
    let mut generated = String::from("pub static ASSETS: &[(&str, &str, &[u8])] = &[\n");
    if dist.exists() {
        visit(dist, dist, &mut generated);
    }
    generated.push_str("];\n");
    fs::write(
        Path::new(&env::var_os("OUT_DIR").unwrap()).join("assets.rs"),
        generated,
    )
    .unwrap();
}
