use axum::{
    body::Bytes,
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;

use crate::codec;
use crate::stats::ServiceStats;

#[derive(Clone)]
pub struct AppState {
    pub stats: Arc<ServiceStats>,
}

#[derive(Serialize)]
pub struct DecodeResponse {
    #[serde(rename = "type")]
    pub frame_type: u8,
    pub seq: u32,
    pub payload: String,
}

#[derive(Deserialize)]
pub struct EncodeRequest {
    #[serde(rename = "type")]
    pub frame_type: u8,
    pub seq: u32,
    pub payload: String,
}

#[derive(Serialize)]
pub struct ErrorResponse {
    pub error: String,
}

#[derive(Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub requests_decoded: u64,
    pub requests_encoded: u64,
}

pub fn build_router(state: AppState) -> Router {
    Router::new()
        .route("/decode", post(handle_decode))
        .route("/encode", post(handle_encode))
        .route("/healthz", get(handle_health))
        .route("/stats", get(handle_stats))
        .with_state(state)
}

async fn handle_decode(
    State(state): State<AppState>,
    body: Bytes,
) -> Response {
    state.stats.record_decode_attempt();

    match codec::decode(&body) {
        Ok(frame) => {
            state.stats.record_decode_success();
            let resp = DecodeResponse {
                frame_type: frame.frame_type,
                seq: frame.seq,
                payload: frame.payload_hex(),
            };
            Json(resp).into_response()
        }
        Err(e) => {
            state.stats.record_decode_failure();
            let msg = format!("{}", e);
            let resp = ErrorResponse { error: msg };
            (StatusCode::BAD_REQUEST, Json(resp)).into_response()
        }
    }
}

async fn handle_encode(
    State(state): State<AppState>,
    Json(req): Json<EncodeRequest>,
) -> Response {
    state.stats.record_encode_attempt();

    match codec::encode_from_parts(req.frame_type, req.seq, &req.payload) {
        Ok(bytes) => {
            state.stats.record_encode_success();
            bytes.into_response()
        }
        Err(e) => {
            state.stats.record_encode_failure();
            let msg = format!("{}", e);
            let resp = ErrorResponse { error: msg };
            (StatusCode::BAD_REQUEST, Json(resp)).into_response()
        }
    }
}

async fn handle_health(State(state): State<AppState>) -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "ok".to_string(),
        requests_decoded: state.stats.decode_attempts(),
        requests_encoded: state.stats.encode_attempts(),
    })
}

async fn handle_stats(State(state): State<AppState>) -> Json<serde_json::Value> {
    Json(state.stats.as_json())
}
