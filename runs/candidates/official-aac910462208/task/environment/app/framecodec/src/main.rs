// main.rs - Entry point for the framecodec service
mod codec;
mod frame;
mod server;
mod stats;
mod util;

use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .init();

    let port: u16 = std::env::var("FRAMECODEC_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(7000);

    tracing::info!("starting framecodec service on port {}", port);
    server::run_server(port).await?;
    Ok(())
}
