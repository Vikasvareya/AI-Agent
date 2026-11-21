# Live Cognitive Activity

## Status

The chat runtime exposes real, owner-scoped cognitive activity events for
conversation messages. It does not expose hidden chain-of-thought or generate
artificial progress percentages.

The existing in-process `EventBus` carries live workflow and activity events.
`ChatStore` persists ordered activity history for replay.

## Event schema

Every activity event contains:

- `event_id`
- `run_id`
- `conversation_id`
- optional `task_id`
- optional `agent_id`
- optional `parent_task_id`
- `event_type`
- `status`
- `summary`
- timezone-aware `timestamp`
- `sequence_number`
- `visibility`
- `metadata`

`event_id` provides duplicate detection. Sequence numbers are assigned per
conversation in the durable store.

## Taxonomy

The current chat implementation emits:

- `request.received`, `request.validated`
- `cognitive.perception.started/completed`
- `cognitive.memory.started/completed`
- `cognitive.planning.started/completed`
- `cognitive.reasoning.started/completed`
- `response.started/completed/failed`
- `execution.completed/failed`
- `research.started/source.discovered/completed` when opted-in web search runs

Tool, agent, coding, testing, and workflow taxonomies remain available for
future real integrations. UI summaries never imply that an operation occurred
when no backend event was produced.

## Persistence and authorization

Events are stored in `agent_activity_events` with a hashed owner identity.
History can be retrieved only for conversations owned by the caller.

- `GET /v1/chat/conversations/{conversation_id}/activity`
- `GET /v1/chat/conversations/{conversation_id}/activity?run_id={run_id}`
- `GET /v1/chat/conversations/{conversation_id}/activity/events?run_id={run_id}`

The last route is an SSE stream. It sends a persisted snapshot first and then
live events for the subscribed run. It does not expose operator-only events.

## Frontend behavior

The chat UI renders a compact activity timeline while a message is sending.
It deduplicates events by `event_id`, orders them by `sequence_number`, and
keeps completed or failed steps visible.

Only the chat response itself is streamed to the UI today: provider responses
remain non-streaming at the model adapter. The activity stream is separate
from answer content.

## Limits

- Event delivery is process-local through the existing EventBus.
- No WebSocket or cross-replica fan-out is implemented.
- SSE reconnection should reload persisted history.
- No cancellation button or unsafe retry is implied.
- Tool, code, research, test, and agent detail previews require their real
  backend event producers and are not fabricated in the UI.
