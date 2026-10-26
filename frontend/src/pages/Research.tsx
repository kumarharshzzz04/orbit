
 // ORBIT Frontend - Research Page
 // Research overview with evidence cards and agent insights

import {  useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  BookOpen,
  Search,
  Filter,
  Brain,
  ExternalLink,
} from 'lucide-react';
import { format } from 'date-fns';

import { useOrbitStore } from '@/stores/useOrbitStore';
import { Card, CardContent } from '@/components/ui/Card';

interface EvidenceCard {
  id: string;
  mission_id: string;
  hypothesis_id?: string;
  agent: string;
  title: string;
  summary: string;
  citations: string[];
  created_at: string;
}

const agentOptions = [
  { value: 'all', label: 'All Agents' },
  { value: 'researcher', label: 'Researcher' },
  { value: 'hypothesizer', label: 'Hypothesizer' },
  { value: 'skeptic', label: 'Skeptic' },
  { value: 'experimenter', label: 'Experimenter' },
  { value: 'evaluator', label: 'Evaluator' },
  { value: 'orchestrator', label: 'Orchestrator' },
];

export function Research() {
  const { messages } = useOrbitStore();

  const [search, setSearch] = useState('');
  const [agentFilter, setAgentFilter] = useState('all');

  // Build evidence cards from actual agent messages.
  const evidenceCards = useMemo<EvidenceCard[]>(() => {
    return messages
      .filter((message) => message.type === 'evidence_card')
      .map((message) => ({
        id: message.id,
        mission_id: message.mission_id,
        hypothesis_id: message.refs?.[0],
        agent: message.agent,
        title: message.body.split('\n')[0] || 'Evidence Card',
        summary: message.body.split('\n').slice(1).join('\n') || message.body,
        citations: message.refs ?? [],
        created_at: message.timestamp,
      }));
  }, [messages]);

  const filteredCards = useMemo(() => {
    return evidenceCards.filter((card) => {
      const query = search.toLowerCase();

      const matchesSearch =
        card.title.toLowerCase().includes(query) ||
        card.summary.toLowerCase().includes(query) ||
        card.agent.toLowerCase().includes(query);

      const matchesAgent =
        agentFilter === 'all' || card.agent === agentFilter;

      return matchesSearch && matchesAgent;
    });
  }, [evidenceCards, search, agentFilter]);

  if (messages.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-orbit-text-primary">
            Research Library
          </h1>
          <p className="text-orbit-text-secondary mt-1">
            Evidence cards and insights from agent research activities
          </p>
        </div>

        <Card className="p-12 text-center">
          <BookOpen className="h-16 w-16 mx-auto mb-4 opacity-30" />
          <p className="text-orbit-text-secondary text-lg">
            No research activity available
          </p>
          <p className="text-sm text-orbit-text-tertiary mt-1">
            Start a mission to generate research evidence
          </p>
          <Link
            to="/missions/new"
            className="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-lg bg-orbit-accent-primary text-white hover:opacity-90 transition-opacity"
          >
            Create Mission
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-orbit-text-primary">
            Research Library
          </h1>
          <p className="text-orbit-text-secondary mt-1">
            Evidence cards and insights from agent research activities
          </p>
        </div>

        <Link
          to="/live"
          className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-orbit-accent-primary text-white hover:opacity-90 transition-opacity"
        >
          <Brain className="h-4 w-4" aria-hidden="true" />
          Live Operations
        </Link>
      </div>

      {/* Search and Filter */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search
              className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-orbit-text-tertiary"
              aria-hidden="true"
            />
            <input
              type="text"
              placeholder="Search evidence cards..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="input-field pl-10"
            />
          </div>

          <div className="relative">
            <Filter
              className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-orbit-text-tertiary"
              aria-hidden="true"
            />
            <select
              value={agentFilter}
              onChange={(event) => setAgentFilter(event.target.value)}
              className="input-field pl-10 pr-8 appearance-none"
            >
              {agentOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      {/* Evidence Cards */}
      {filteredCards.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredCards.map((card) => (
            <Card
              key={card.id}
              className="h-full hover:border-orbit-border-secondary transition-colors"
            >
              <CardContent className="p-5 flex flex-col h-full">
                <div className="flex items-center justify-between gap-2 mb-3">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full"
                      style={{
                        backgroundColor: `var(--orbit-agent-${card.agent})`,
                      }}
                    />
                    <span className="font-medium text-sm capitalize">
                      {card.agent}
                    </span>
                  </div>
                </div>

                <h4 className="font-semibold text-orbit-text-primary mb-2 line-clamp-2">
                  {card.title}
                </h4>

                <p className="text-orbit-text-secondary text-sm flex-1 mb-3 line-clamp-3">
                  {card.summary}
                </p>

                {card.citations.length > 0 && (
                  <div className="mb-3">
                    <p className="text-xs text-orbit-text-tertiary mb-1">
                      References:
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {card.citations.map((citation, index) => (
                        <span
                          key={`${card.id}-${citation}-${index}`}
                          className="text-xs px-2 py-1 rounded bg-orbit-bg-tertiary text-orbit-text-secondary"
                        >
                          {citation}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex items-center justify-between pt-3 border-t border-orbit-border-primary/50">
                  <span className="text-xs text-orbit-text-tertiary">
                    {format(new Date(card.created_at), 'MMM dd, HH:mm')}
                  </span>

                  <Link
                    to={`/missions/${card.mission_id}`}
                    className="inline-flex items-center gap-1 text-sm text-orbit-text-secondary hover:text-orbit-text-primary transition-colors"
                  >
                    <ExternalLink
                      className="h-3 w-3"
                      aria-hidden="true"
                    />
                    Mission
                  </Link>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card className="p-12 text-center">
          <BookOpen className="h-16 w-16 mx-auto mb-4 opacity-30" />
          <p className="text-orbit-text-secondary text-lg">
            No evidence cards found
          </p>
          <p className="text-sm text-orbit-text-tertiary mt-1">
            {search || agentFilter !== 'all'
              ? 'Try adjusting your search or filter'
              : 'No evidence cards have been generated yet'}
          </p>
        </Card>
      )}

      {/* Agent Insights Summary */}
      <div>
        <h2 className="text-xl font-semibold text-orbit-text-primary mb-4">
          Agent Activity
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {agentOptions
            .filter((agent) => agent.value !== 'all')
            .map((agent) => {
              const agentCards = evidenceCards.filter(
                (card) => card.agent === agent.value
              );

              return (
                <Card key={agent.value} className="p-4">
                  <div className="flex items-center gap-3 mb-3">
                    <span
                      className="w-10 h-10 rounded-lg flex items-center justify-center"
                      style={{
                        backgroundColor: `color-mix(in srgb, var(--orbit-agent-${agent.value}) 20%, transparent)`,
                      }}
                    >
                      <span
                        className="w-5 h-5 rounded-full"
                        style={{
                          backgroundColor: `var(--orbit-agent-${agent.value})`,
                        }}
                      />
                    </span>

                    <div>
                      <p className="font-medium capitalize">
                        {agent.label}
                      </p>
                      <p className="text-xs text-orbit-text-tertiary">
                        {agentCards.length} evidence cards
                      </p>
                    </div>
                  </div>

                  <div className="p-3 bg-orbit-bg-tertiary rounded text-center">
                    <p className="text-2xl font-bold text-orbit-text-primary">
                      {agentCards.length}
                    </p>
                    <p className="text-xs text-orbit-text-tertiary">
                      Evidence Cards
                    </p>
                  </div>
                </Card>
              );
            })}
        </div>
      </div>
    </div>
  );
}
