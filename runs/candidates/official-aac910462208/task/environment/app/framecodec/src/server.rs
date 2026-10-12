// server.rs - HTTP control plane for the framecodec service
use axum::{
    body::Bytes,
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::post,
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::net::TcpListener;

use crate::codec;
use crate::frame::FrameError;
use crate::frame::Frame;
use crate::stats::ServiceStats;

#[derive(Clone)]
pub struct AppState {
    pub stats: Arc<ServiceStats>,
}

#[derive(Debug, Deserialize)]
pub struct EncodeRequest {
    #[serde(rename = "type")]
    pub frame_type: u8,
    pub seq: u32,
    pub payload: String,
}

#[derive(Debug, Serialize)]
pub struct DecodeResponse {
    #[serde(rename = "type")]
    pub frame_type: u8,
    pub seq: u32,
    pub payload: String,
}

#[derive(Debug, Serialize)]
pub struct ErrorResponse {
    pub error: String,
}

pub async fn run_server(port: u16) -> anyhow::Result<()> {
    let stats = Arc::new(ServiceStats::new());
    let state = AppState { stats };

    let app = Router::new()
        .route("/encode", post(handle_encode))
        .route("/decode", post(handle_decode))
        .route("/healthz", axum::routing::get(handle_health))
        .route("/stats", axum::routing::get(handle_stats))
        .with_state(state);

    let addr = format!("0.0.0.0:{}", port);
    let listener = TcpListener::bind(&addr).await?;
    tracing::info!("framecodec service listening on {}", addr);
    axum::serve(listener, app).await?;
    Ok(())
}

async fn handle_health() -> impl IntoResponse {
    (StatusCode::OK, "ok")
}

async fn handle_stats(
    State(state): State<AppState>,
) -> impl IntoResponse {
    let s = state.stats.snapshot();
    Json(s)
}

async fn handle_encode(
    State(state): State<AppState>,
    Json(req): Json<EncodeRequest>,
) -> Response {
    state.stats.inc_encode();

    let payload_bytes = match hex::decode(&req.payload) {
        Ok(b) => b,
        Err(e) => {
            state.stats.inc_error();
            let body = serde_json::json!({ "error": format!("invalid hex payload: {}", e) });
            return (StatusCode::BAD_REQUEST, Json(body)).into_response();
        }
    };

    let frame = Frame::new(req.frame_type, req.seq, payload_bytes);

    match codec::encode(&frame) {
        Ok(bytes) => {
            state.stats.inc_encode_ok();
            (StatusCode::OK, bytes).into_response()
        }
        Err(e) => {
            state.stats.inc_error();
            let body = serde_json::json!({ "error": format!("encode error: {}", e) });
            (StatusCode::INTERNAL_SERVER_ERROR, Json(body)).into_response()
        }
    }
}

async fn handle_decode(
    State(state): State<AppState>,
    body: Bytes,
) -> Response {
    state.stats.inc_decode();

    // Validate minimum frame size; the MultiByteLengthPrefix error name is
    // used here for the body-too-short case (misleading naming from original author)
    if body.len() < crate::frame::HEADER_SIZE {
        state.stats.inc_error();
        tracing::warn!(
            "decode request body too short ({} bytes): {}",
            body.len(),
            FrameError::MultiByteLengthPrefix
        );
        let body = serde_json::json!({ "error": FrameError::MultiByteLengthPrefix.to_string() });
        return (StatusCode::BAD_REQUEST, Json(body)).into_response();
    }

    match codec::decode(&body) {
        Ok(frame) => {
            state.stats.inc_decode_ok();
            let resp = DecodeResponse {
                frame_type: frame.frame_type,
                seq: frame.seq,
                payload: hex::encode(&frame.payload),
            };
            (StatusCode::OK, Json(resp)).into_response()
        }
        Err(e) => {
            state.stats.inc_error();
            tracing::warn!("decode error: {}", e);
            let body = serde_json::json!({ "error": e.to_string() });
            (StatusCode::UNPROCESSABLE_ENTITY, Json(body)).into_response()
        }
    }
}
