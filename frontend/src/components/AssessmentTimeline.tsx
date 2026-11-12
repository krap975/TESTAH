import { useEffect, useRef, useState } from 'react';
import { describeEvent } from '../services/assessmentGraph';
import type { RunEvent } from '../types/assessments';

export function AssessmentTimeline({ events, selectedId, select }: { events: RunEvent[]; selectedId: string | undefined; select: (id: string) => void }) {
  const list = useRef<HTMLOListElement>(null); const [follow, setFollow] = useState(true);
  useEffect(() => { if (follow && list.current) list.current.scrollTop = list.current.scrollHeight; }, [events, follow]);
  return <section className="panel monitor-timeline" aria-label="Chronological event timeline">
    <div className="section-header"><h2>Event timeline</h2><button type="button" onClick={() => setFollow(true)} disabled={follow}>Follow latest</button></div>
    <p className="form-help p-4">{follow ? 'Following the latest visible events.' : 'Auto-scroll paused while you explore earlier events.'}</p>
    <ol ref={list} className="monitor-event-list" onScroll={() => { const element = list.current; if (element) setFollow(element.scrollHeight - element.scrollTop - element.clientHeight < 40); }}>
      {events.length === 0 ? <li className="p-4 muted">No events in this selection.</li> : events.map(event => {
        const detail = describeEvent(event);
        return <li key={event.id}><button type="button" className={'monitor-event interaction-' + detail.outcome + (selectedId === event.id ? ' selected' : '')}
          onClick={() => { setFollow(false); select(event.id); }}><span className="monitor-event-title">#{event.sequence} · {event.event_type}<span>{detail.outcome}</span></span>
          <span className="monitor-event-meta"><time dateTime={event.created_at}>{new Date(event.created_at).toLocaleTimeString()}</time> · {detail.actor}</span>
          <span>{detail.description}</span></button></li>;
      })}
    </ol>
  </section>;
}
