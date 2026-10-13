mod codec;
mod frame;
mod server;
mod stats;
mod util;

use std::net::SocketAddr;
use std::sync::Arc;

use server::{AppState, build_router};
use stats::ServiceStats;

#[tokio::main]
async fn main() {
    let port: u16 = std::env::var("FRAMECODEC_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(7000);

    let stats = Arc::new(ServiceStats::new());
    let state = AppState { stats };
    let router = build_router(state);

    let addr = SocketAddr::from(([0, 0, 0, 0], port));

    eprintln!("framecodec service listening on {}", addr);

    axum::Server::bind(&addr)
        .serve(router.into_make_service())
        .await
        .unwrap_or_else(|e| {
            eprintln!("Server error: {}", e);
            std::process::exit(1);
        });
}
