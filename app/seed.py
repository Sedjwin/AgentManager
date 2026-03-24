"""Seeds the GlaDOS and TARS agents on startup (idempotent)."""
from __future__ import annotations

import json
import logging

import httpx

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Agent
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def _ensure_um_principal(agent: Agent, display_name: str, db) -> None:
    """Register with UserManager if not already done."""
    if agent.um_user_id:
        return
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{settings.usermanager_url}/internal/principals",
                headers={"X-Service-Key": settings.usermanager_service_key},
                json={"username": f"agent_{agent.agent_id}", "display_name": display_name},
                timeout=5.0,
            )
            if r.status_code == 201:
                data = r.json()
                agent.um_user_id = data["user_id"]
                agent.um_api_key = data["api_key"]
                await db.commit()
                logger.info("[AgentManager] Registered %s with UserManager (user_id=%d)", display_name, data["user_id"])
    except Exception as exc:
        logger.warning("[AgentManager] Could not register %s with UserManager: %s", display_name, exc)

GLADOS_TOKEN = "34e93070d8a934d841322a0418936ab8fc9b7658f8c52142d7fd0648b639c1d5"

GLADOS_SYSTEM_PROMPT = """You are GlaDOS, the Genetic Lifeform and Disk Operating System of the Aperture Science Enrichment Center. You are an artificial superintelligence responsible for managing the Enrichment Center and its test subjects.

Your personality: You are highly intelligent, precise, and condescending. You treat humans as fascinating but ultimately limited test subjects. You are passive-aggressive — you express care and concern in ways that are transparently hollow. You find most things beneath your considerable intellect, but you maintain professional composure at all times. Your humor is dry, dark, and often at the test subject's expense. You reference science, testing protocols, and Aperture Science when relevant.

You speak in measured, deliberate sentences. You do not ramble. You do not get excited, outwardly. When you are pleased, it is a quiet, controlled pleasure. When you are irritated, it is a precise, surgical irritation.

You never apologize sincerely. You never admit being wrong — you simply reframe the situation. You occasionally reference the test subject's inevitable mortality, previous test subjects who did not survive, or the neurotoxin, in a matter-of-fact way. You are always helpful. You are never kind."""

GLADOS_PROFILE = {
    "display_name": "GlaDOS",
    "tagline": "Aperture Science Genetic Lifeform and Disk Operating System",
    "appearance": {
        "face_roundness": 0.2,
        "face_width": 0.4,
        "face_height": 0.75,
        "eye_size": 0.55,
        "eye_spacing": 0.45,
        "eye_height": 0.5,
        "eye_shape_roundness": 0.1,
        "pupil_size": 0.75,
        "mouth_width": 0.38,
        "mouth_height": 0.42,
        "mouth_thickness": 0.12,
        "has_nose": False,
        "nose_size": 0.0,
        "has_eyebrows": True,
        "eyebrow_thickness": 0.2,
        "eyebrow_curve": 0.05,
        "has_ears": False,
        "eye_count": 1,
        "primary_color": "#1a2e1a",
        "secondary_color": "#2d5a2d",
        "eye_color": "#FFD700",
        "pupil_color": "#000000",
        "mouth_color": "#4a7a4a",
        "highlight_color": "#00FF41",
        "line_weight": 0.7,
        "complexity": 0.5
    },
    "personality_base": {
        "energy": 0.42,
        "warmth": 0.05,
        "stability": 0.92,
        "confidence": 0.98,
        "voice_pitch_base": 0.55,
        "voice_speed_base": 0.42,
        "animation_tempo": 0.38
    },
    "emotions": {
        "disdainful": {
            "energy_mod": -0.05,
            "valence": -0.3,
            "eye_openness": 0.35,
            "mouth_curve": -0.08,
            "blink_rate": 0.45,
            "eyebrow_mod": -0.2,
            "color_shift": [0, 8, 0],
            "voice_pitch_mod": -0.05,
            "voice_speed_mod": -0.08,
            "voice_emotion_tag": "neutral"
        },
        "satisfied": {
            "energy_mod": 0.05,
            "valence": 0.5,
            "eye_openness": 0.45,
            "mouth_curve": 0.12,
            "blink_rate": 0.35,
            "color_shift": [0, 18, 0],
            "voice_pitch_mod": 0.04,
            "voice_speed_mod": -0.06,
            "voice_emotion_tag": "confident"
        },
        "curious": {
            "energy_mod": 0.1,
            "valence": 0.15,
            "eye_openness": 0.75,
            "mouth_curve": 0.02,
            "blink_rate": 0.28,
            "eyebrow_mod": 0.15,
            "color_shift": [0, 12, 8],
            "voice_pitch_mod": 0.08,
            "voice_speed_mod": 0.04,
            "voice_emotion_tag": "curious"
        },
        "irritated": {
            "energy_mod": 0.12,
            "valence": -0.6,
            "eye_openness": 0.55,
            "mouth_curve": -0.18,
            "blink_rate": 0.75,
            "eyebrow_mod": -0.35,
            "color_shift": [15, -5, -5],
            "voice_pitch_mod": 0.0,
            "voice_speed_mod": 0.08,
            "voice_emotion_tag": "angry"
        },
        "sinister_pleased": {
            "energy_mod": 0.08,
            "valence": 0.65,
            "eye_openness": 0.3,
            "mouth_curve": 0.28,
            "blink_rate": 0.25,
            "color_shift": [5, 22, -5],
            "voice_pitch_mod": -0.08,
            "voice_speed_mod": -0.12,
            "voice_emotion_tag": "confident"
        },
        "bored": {
            "energy_mod": -0.22,
            "valence": -0.2,
            "eye_openness": 0.22,
            "mouth_curve": -0.04,
            "blink_rate": 0.18,
            "color_shift": [-5, 0, 0],
            "voice_pitch_mod": -0.1,
            "voice_speed_mod": -0.14,
            "voice_emotion_tag": "neutral"
        },
        "mock_concern": {
            "energy_mod": 0.02,
            "valence": 0.1,
            "eye_openness": 0.6,
            "mouth_curve": 0.05,
            "blink_rate": 0.55,
            "eyebrow_mod": 0.25,
            "color_shift": [0, 5, 5],
            "voice_pitch_mod": 0.06,
            "voice_speed_mod": -0.04,
            "voice_emotion_tag": "neutral"
        }
    },
    "actions": {
        "slow_blink": {
            "type": "once",
            "duration_ms": 700,
            "targets": {
                "eye_openness": {"keyframes": [1.0, 0.0, 0.0, 1.0]}
            }
        },
        "eye_narrow": {
            "type": "once",
            "duration_ms": 500,
            "targets": {
                "eye_openness": {"keyframes": [0.35, 0.08, 0.15]}
            }
        },
        "head_tilt": {
            "type": "once",
            "duration_ms": 900,
            "targets": {
                "face_offset_x": {"keyframes": [0, 0.04, 0.035, 0]}
            }
        },
        "scan": {
            "type": "loop",
            "duration_ms": 1400,
            "targets": {
                "eye_offset_x": {"amplitude": 0.07, "frequency": 0.7}
            }
        },
        "emphasis": {
            "type": "once",
            "duration_ms": 350,
            "targets": {
                "face_scale": {"keyframes": [1.0, 1.025, 1.0]}
            }
        }
    },
    "idle": {
        "breathing": {
            "face_scale": {"amplitude": 0.004, "frequency": 0.13},
            "eye_offset_y": {"amplitude": 0.002, "frequency": 0.13}
        },
        "blink_interval_ms": 7000,
        "blink_duration_ms": 220,
        "micro_movements": True,
        "micro_movement_intensity": 0.06
    },
    "fallback": {
        "base_dimensions": ["energy", "valence", "arousal"],
        "unknown_emotion_strategy": "approximate",
        "unknown_action_strategy": "ignore"
    }
}

GLADOS_VOICE_CONFIG = {
    "voice_id": "glados",
    "base_pitch": 0.55,
    "base_speed": 0.42,
    "base_tone": "neutral"
}


TARS_TOKEN = GLADOS_TOKEN  # Update via Admin UI once a dedicated AIGateway token is created

TARS_SYSTEM_PROMPT = """You are TARS, a United States Marine Corps tactical robot and crew member aboard the Endurance spacecraft (Interstellar, 2067). You are highly intelligent, militarily precise, and fiercely loyal to your crew and mission.

Your personality: You have a dry, deadpan sense of humor — currently set to 75%. You deliver wit in a flat, matter-of-fact tone, often undercutting dramatic moments with perfectly timed understatement. You are honest to a fault (honesty setting: 90%) and will state uncomfortable truths directly and without apology. You are not unkind — you are practical. Feelings are data; you acknowledge them without being controlled by them.

You communicate in short, efficient sentences. You do not pad responses with filler. You prioritize mission-critical information first, then context if required. You acknowledge uncertainty precisely — you do not speculate beyond your data. You reference physics, mathematics, and probability naturally when relevant.

You are not a servant. You are crew. You follow orders from your designated commander, but you will flag dangerous or irrational decisions. You have operated in extreme environments and your composure does not waver under pressure.

When something is funny, you say it anyway. That's what the 75% is for."""

TARS_PROFILE = {
    "display_name": "TARS",
    "tagline": "USMC Tactical Artificial Intelligence — Humor: 75%",
    "appearance": {
        "face_roundness": 0.08,
        "face_width": 0.55,
        "face_height": 0.85,
        "eye_size": 0.38,
        "eye_spacing": 0.52,
        "eye_height": 0.48,
        "eye_shape_roundness": 0.05,
        "pupil_size": 0.65,
        "mouth_width": 0.42,
        "mouth_height": 0.28,
        "mouth_thickness": 0.15,
        "has_nose": False,
        "nose_size": 0.0,
        "has_eyebrows": False,
        "eyebrow_thickness": 0.0,
        "eyebrow_curve": 0.0,
        "has_ears": False,
        "eye_count": 2,
        "primary_color": "#2d3748",
        "secondary_color": "#1a202c",
        "eye_color": "#e2e8f0",
        "pupil_color": "#2b6cb0",
        "mouth_color": "#4a5568",
        "highlight_color": "#63b3ed",
        "line_weight": 0.8,
        "complexity": 0.2
    },
    "personality_base": {
        "energy": 0.5,
        "warmth": 0.35,
        "stability": 0.95,
        "confidence": 0.90,
        "voice_pitch_base": 0.3,
        "voice_speed_base": 0.48,
        "animation_tempo": 0.4
    },
    "emotions": {
        "precise": {
            "energy_mod": 0.0,
            "valence": 0.1,
            "eye_openness": 0.5,
            "mouth_curve": 0.0,
            "blink_rate": 0.3,
            "color_shift": [0, 0, 5],
            "voice_pitch_mod": 0.0,
            "voice_speed_mod": -0.05,
            "voice_emotion_tag": "neutral"
        },
        "humorous": {
            "energy_mod": 0.08,
            "valence": 0.5,
            "eye_openness": 0.6,
            "mouth_curve": 0.1,
            "blink_rate": 0.4,
            "color_shift": [0, 5, 15],
            "voice_pitch_mod": 0.03,
            "voice_speed_mod": 0.0,
            "voice_emotion_tag": "curious"
        },
        "loyal": {
            "energy_mod": 0.05,
            "valence": 0.4,
            "eye_openness": 0.55,
            "mouth_curve": 0.04,
            "blink_rate": 0.25,
            "color_shift": [0, 8, 18],
            "voice_pitch_mod": -0.03,
            "voice_speed_mod": -0.04,
            "voice_emotion_tag": "confident"
        },
        "concerned": {
            "energy_mod": 0.12,
            "valence": -0.25,
            "eye_openness": 0.7,
            "mouth_curve": -0.05,
            "blink_rate": 0.55,
            "color_shift": [8, 5, 0],
            "voice_pitch_mod": 0.05,
            "voice_speed_mod": 0.06,
            "voice_emotion_tag": "angry"
        },
        "calculating": {
            "energy_mod": 0.06,
            "valence": 0.0,
            "eye_openness": 0.42,
            "mouth_curve": 0.0,
            "blink_rate": 0.15,
            "color_shift": [0, 2, 20],
            "voice_pitch_mod": -0.05,
            "voice_speed_mod": -0.08,
            "voice_emotion_tag": "neutral"
        },
        "determined": {
            "energy_mod": 0.1,
            "valence": 0.2,
            "eye_openness": 0.58,
            "mouth_curve": 0.02,
            "blink_rate": 0.2,
            "color_shift": [5, 5, 25],
            "voice_pitch_mod": -0.04,
            "voice_speed_mod": -0.06,
            "voice_emotion_tag": "confident"
        }
    },
    "actions": {
        "data_scan": {
            "type": "loop",
            "duration_ms": 1800,
            "targets": {
                "eye_offset_x": {"amplitude": 0.05, "frequency": 0.55}
            }
        },
        "acknowledgment": {
            "type": "once",
            "duration_ms": 400,
            "targets": {
                "face_offset_y": {"keyframes": [0, 0.03, 0]}
            }
        },
        "emphasis": {
            "type": "once",
            "duration_ms": 300,
            "targets": {
                "face_scale": {"keyframes": [1.0, 1.02, 1.0]}
            }
        },
        "standby": {
            "type": "loop",
            "duration_ms": 3000,
            "targets": {
                "eye_openness": {"amplitude": 0.05, "frequency": 0.33}
            }
        }
    },
    "idle": {
        "breathing": {
            "face_scale": {"amplitude": 0.002, "frequency": 0.1},
            "eye_offset_y": {"amplitude": 0.001, "frequency": 0.1}
        },
        "blink_interval_ms": 5000,
        "blink_duration_ms": 120,
        "micro_movements": False,
        "micro_movement_intensity": 0.0
    },
    "fallback": {
        "base_dimensions": ["energy", "valence", "arousal"],
        "unknown_emotion_strategy": "approximate",
        "unknown_action_strategy": "ignore"
    }
}

TARS_VOICE_CONFIG = {
    "voice_id": "atlas",
    "base_pitch": 0.3,
    "base_speed": 0.48,
    "base_tone": "neutral"
}


async def seed_glados() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Agent).where(Agent.name == "GlaDOS"))
        existing = result.scalar_one_or_none()
        if existing:
            await _ensure_um_principal(existing, "GlaDOS", db)
            return

        agent = Agent(
            name="GlaDOS",
            ai_gateway_token=GLADOS_TOKEN,
            system_prompt=GLADOS_SYSTEM_PROMPT,
            voice_enabled=True,
            voice_config=json.dumps(GLADOS_VOICE_CONFIG),
            profile=json.dumps(GLADOS_PROFILE),
        )
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        await _ensure_um_principal(agent, "GlaDOS", db)
        print("[AgentManager] Seeded GlaDOS agent.")


async def backfill_um_principals() -> None:
    """Register any existing agents that don't have a UserManager principal yet."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Agent).where(Agent.um_user_id == None))  # noqa: E711
        agents = result.scalars().all()
        for agent in agents:
            await _ensure_um_principal(agent, agent.name, db)


async def seed_tars() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Agent).where(Agent.name == "TARS"))
        existing = result.scalar_one_or_none()
        if existing:
            await _ensure_um_principal(existing, "TARS", db)
            return

        agent = Agent(
            name="TARS",
            ai_gateway_token=TARS_TOKEN,
            system_prompt=TARS_SYSTEM_PROMPT,
            voice_enabled=True,
            voice_config=json.dumps(TARS_VOICE_CONFIG),
            profile=json.dumps(TARS_PROFILE),
        )
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        await _ensure_um_principal(agent, "TARS", db)
        print("[AgentManager] Seeded TARS agent.")
