// ORBIT Frontend - Settings Page
// Application settings and configuration

import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  User,
  Palette,
  Wifi,
  Shield,
  Save,
} from 'lucide-react';
import { useOrbitStore } from '@/stores/useOrbitStore';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import type { BadgeProps } from '@/components/ui/Badge';
import { Tabs, TabList, TabTrigger, TabContent } from '@/components/ui/Tabs';
import { toast } from 'sonner';
import { useTheme } from '@/hooks/useTheme';
import { apiClient } from '@/api/client';

const profileSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  email: z.string().email('Invalid email'),
});

const preferencesSchema = z.object({
  theme: z.enum(['dark', 'light', 'system']),
  auto_refresh: z.boolean(),
  compact_sidebar: z.boolean(),
  notifications_enabled: z.boolean(),
  email_notifications: z.boolean(),
});

const apiSchema = z.object({
  api_base_url: z.string().url('Invalid URL'),
  ws_base_url: z.string().url('Invalid URL'),
  request_timeout: z.number().min(1000).max(120000),
});

type ProfileFormData = z.infer<typeof profileSchema>;
type PreferencesFormData = z.infer<typeof preferencesSchema>;
type ApiFormData = z.infer<typeof apiSchema>;

interface HealthStatus {
  rest_api: 'connected' | 'disconnected' | 'unknown';
  websocket: 'connected' | 'disconnected' | 'unknown';
  database: 'healthy' | 'unhealthy' | 'unknown';
  ml_sandbox: 'ready' | 'not_ready' | 'unknown';
}

export function SettingsPage() {
  const {
    setTheme: setStoreTheme,
    sidebarCompact,
    setSidebarCompact
  } = useOrbitStore();
  const { setTheme: setResolvedTheme } = useTheme();
  const [saving, setSaving] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('profile');
  const [healthStatus, setHealthStatus] = useState<HealthStatus>({
    rest_api: 'unknown',
    websocket: 'unknown',
    database: 'unknown',
    ml_sandbox: 'unknown',
  });
  const [healthLoading, setHealthLoading] = useState(true);

  // Initialize forms with actual store values
  const {
    register: registerProfile,
    handleSubmit: handleSubmitProfile,
    formState: { errors: profileErrors },
  } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      name: 'Mission Operator',
      email: 'operator@orbit.local',
    },
  });

  const {
    register: registerPrefs,
    handleSubmit: handleSubmitPrefs,
    watch: watchPrefs,
    setValue: setPrefsValue,
    formState: { errors: prefsErrors },
  } = useForm<PreferencesFormData>({
    resolver: zodResolver(preferencesSchema),
    defaultValues: {
      theme: 'system',
      auto_refresh: true,
      compact_sidebar: sidebarCompact,
      notifications_enabled: true,
      email_notifications: false,
    },
  });

  const {
    register: registerApi,
    handleSubmit: handleSubmitApi,
    formState: { errors: apiErrors },
  } = useForm<ApiFormData>({
    resolver: zodResolver(apiSchema),
    defaultValues: {
      api_base_url: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
      ws_base_url: import.meta.env.VITE_WS_BASE_URL || 'ws://127.0.0.1:8000',
      request_timeout: 30000,
    },
  });

  // Sync theme from store on mount
  useEffect(() => {
    const storedTheme = localStorage.getItem('orbit-theme');
    if (storedTheme === 'dark' || storedTheme === 'light') {
      setPrefsValue('theme', storedTheme, { shouldValidate: true });
    } else {
      setPrefsValue('theme', 'system', { shouldValidate: true });
    }
  }, [setPrefsValue]);

  // Check backend health on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const health = await apiClient.healthCheck();
        setHealthStatus({
          rest_api: 'connected',
          websocket: 'connected', // Would need separate WS health check
          database: health.database === 'healthy' ? 'healthy' : 'unhealthy',
          ml_sandbox: health.ml_sandbox === 'ready' ? 'ready' : 'not_ready',
        });
      } catch {
        setHealthStatus({
          rest_api: 'disconnected',
          websocket: 'disconnected',
          database: 'unhealthy',
          ml_sandbox: 'not_ready',
        });
      } finally {
        setHealthLoading(false);
      }
    };
    checkHealth();
  }, []);

  const onSaveProfile = async (_data: ProfileFormData) => {
    setSaving('profile');
    try {
      // Profile persistence not yet implemented in backend
      toast.info('Profile saved locally (backend persistence not yet implemented)');
    } catch {
      toast.error('Failed to save profile');
    } finally {
      setSaving(null);
    }
  };

  const onSavePreferences = async (_data: PreferencesFormData) => {
    setSaving('preferences');
    try {
      // Apply theme - get current value from form
      const theme = watchPrefs('theme');
      if (theme === 'dark' || theme === 'light') {
        setStoreTheme(theme);
        setResolvedTheme(theme);
      } else if (theme === 'system') {
        // System theme is handled by useTheme hook
        localStorage.removeItem('orbit-theme');
        const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        setStoreTheme(systemTheme);
        setResolvedTheme(systemTheme);
      }
      // Apply sidebar settings - single source of truth in Zustand
      const compactSidebar = watchPrefs('compact_sidebar');
      setSidebarCompact(compactSidebar);
      // Update form to match store
      setPrefsValue('compact_sidebar', compactSidebar, { shouldValidate: true, shouldDirty: true });

      toast.success('Preferences saved (stored locally)');
    } catch {
      toast.error('Failed to save preferences');
    } finally {
      setSaving(null);
    }
  };

  const onSaveApi = async (_data: ApiFormData) => {
    setSaving('api');
    try {
      // API settings are configured via environment variables
      // This is just local display - actual change requires restart
      toast.info('API settings are configured via environment variables (VITE_API_BASE_URL, VITE_WS_BASE_URL). Restart required.');
    } catch {
      toast.error('Failed to save API settings');
    } finally {
      setSaving(null);
    }
  };

  const getStatusBadge = (status: string) => {
    const statusMap: Record<string, { variant: BadgeProps['variant']; label: string }> = {
      connected: { variant: 'keep', label: 'Connected' },
      disconnected: { variant: 'reject', label: 'Disconnected' },
      healthy: { variant: 'keep', label: 'Healthy' },
      unhealthy: { variant: 'reject', label: 'Unhealthy' },
      ready: { variant: 'keep', label: 'Ready' },
      not_ready: { variant: 'warning', label: 'Not Ready' },
      unknown: { variant: 'default', label: 'Unknown' },
    };
    return statusMap[status] || { variant: 'default', label: status };
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold text-orbit-text-primary">Settings</h1>
        <p className="text-orbit-text-secondary mt-1">
          Configure your ORBIT Mission Control preferences
        </p>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabList className="mb-6">
          <TabTrigger value="profile">
            <User className="h-4 w-4 mr-2" />
            Profile
          </TabTrigger>
          <TabTrigger value="preferences">
            <Palette className="h-4 w-4 mr-2" />
            Preferences
          </TabTrigger>
          <TabTrigger value="api">
            <Wifi className="h-4 w-4 mr-2" />
            API Configuration
          </TabTrigger>
          <TabTrigger value="about">
            <Shield className="h-4 w-4 mr-2" />
            About
          </TabTrigger>
        </TabList>

        {/* Profile Tab */}
        <TabContent value="profile">
          <Card>
            <CardHeader>
              <CardTitle>Profile Information</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmitProfile(onSaveProfile)} className="space-y-4">
                <Input
                  label="Display Name"
                  placeholder="Your name"
                  error={profileErrors.name?.message}
                  {...registerProfile('name')}
                />
                <Input
                  label="Email Address"
                  type="email"
                  placeholder="you@example.com"
                  error={profileErrors.email?.message}
                  {...registerProfile('email')}
                />
                <div className="flex justify-end pt-4 border-t border-orbit-border-primary/50">
                  <Button type="submit" loading={saving === 'profile'}>
                    <Save className="h-4 w-4 mr-2" />
                    Save Profile
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </TabContent>

        {/* Preferences Tab */}
        <TabContent value="preferences">
          <Card>
            <CardHeader>
              <CardTitle>User Preferences</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmitPrefs(onSavePreferences)} className="space-y-6">
                {/* Theme */}
                <div>
                  <label className="label-text">Theme</label>
                  <div className="grid grid-cols-3 gap-3 mt-2">
                    {(['dark', 'light', 'system'] as const).map((t) => (
                      <button
                        key={t}
                        type="button"
                        onClick={() => {
                          setPrefsValue('theme', t, { shouldValidate: true, shouldDirty: true });
                        }}
                        className={`p-4 rounded-lg border-2 transition-all ${
                          watchPrefs('theme') === t
                            ? 'border-orbit-accent-primary bg-orbit-accent-primary/10'
                            : 'border-orbit-border-primary hover:border-orbit-border-secondary'
                        }`}
                      >
                        <div className="flex items-center justify-center gap-2">
                          {t === 'dark' && <span className="text-orbit-text-primary">🌙</span>}
                          {t === 'light' && <span className="text-orbit-text-primary">☀️</span>}
                          {t === 'system' && <span className="text-orbit-text-primary">💻</span>}
                          <span className="font-medium capitalize">{t}</span>
                        </div>
                        <p className="text-xs text-orbit-text-tertiary text-center mt-1">
                          {t === 'dark' ? 'Always dark' : t === 'light' ? 'Always light' : 'Match system'}
                        </p>
                      </button>
                    ))}
                  </div>
                  {prefsErrors.theme && (
                    <p className="mt-1.5 text-sm text-orbit-accent-negative">{prefsErrors.theme.message}</p>
                  )}
                </div>

                {/* UI Preferences */}
                <div className="space-y-4 pt-4 border-t border-orbit-border-primary/50">
                  <h4 className="font-medium text-orbit-text-secondary">Interface</h4>
                  <div className="space-y-3">
                    <label className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Compact Sidebar</p>
                        <p className="text-sm text-orbit-text-tertiary">Reduce sidebar width for more content space</p>
                      </div>
                      <input
                        type="checkbox"
                        {...registerPrefs('compact_sidebar')}
                        onChange={(e) => {
                          registerPrefs('compact_sidebar').onChange(e);
                          setSidebarCompact(e.target.checked);
                        }}
                        className="h-5 w-5 rounded border-orbit-border-primary text-orbit-accent-primary focus:ring-orbit-accent-primary"
                      />
                    </label>
                    <label className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Auto Refresh</p>
                        <p className="text-sm text-orbit-text-tertiary">Automatically refresh data periodically</p>
                      </div>
                      <input
                        type="checkbox"
                        {...registerPrefs('auto_refresh')}
                        className="h-5 w-5 rounded border-orbit-border-primary text-orbit-accent-primary focus:ring-orbit-accent-primary"
                      />
                    </label>
                  </div>
                </div>

                {/* Notifications */}
                <div className="space-y-4 pt-4 border-t border-orbit-border-primary/50">
                  <h4 className="font-medium text-orbit-text-secondary">Notifications</h4>
                  <div className="space-y-3">
                    <label className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Enable Notifications</p>
                        <p className="text-sm text-orbit-text-tertiary">Show toast notifications for events</p>
                      </div>
                      <input
                        type="checkbox"
                        {...registerPrefs('notifications_enabled')}
                        className="h-5 w-5 rounded border-orbit-border-primary text-orbit-accent-primary focus:ring-orbit-accent-primary"
                      />
                    </label>
                    <label className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Email Notifications</p>
                        <p className="text-sm text-orbit-text-tertiary">Receive email updates (requires backend config)</p>
                      </div>
                      <input
                        type="checkbox"
                        {...registerPrefs('email_notifications')}
                        className="h-5 w-5 rounded border-orbit-border-primary text-orbit-accent-primary focus:ring-orbit-accent-primary"
                      />
                    </label>
                  </div>
                </div>

                <div className="flex justify-end pt-4 border-t border-orbit-border-primary/50">
                  <Button type="submit" loading={saving === 'preferences'}>
                    <Save className="h-4 w-4 mr-2" />
                    Save Preferences
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </TabContent>

        {/* API Configuration Tab */}
        <TabContent value="api">
          <Card>
            <CardHeader>
              <CardTitle>API Configuration</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmitApi(onSaveApi)} className="space-y-4">
                <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                  <p className="text-sm text-amber-400">
                    <strong>Note:</strong> API settings are configured via environment variables
                    (<code className="font-mono px-1.5 py-0.5 bg-orbit-bg-primary rounded">VITE_API_BASE_URL</code>,
                    <code className="font-mono px-1.5 py-0.5 bg-orbit-bg-primary rounded">VITE_WS_BASE_URL</code>).
                    Changes here are for display only; restart the application after updating <code className="font-mono px-1.5 py-0.5 bg-orbit-bg-primary rounded">.env</code>.
                  </p>
                </div>

                <Input
                  label="API Base URL"
                  placeholder="http://127.0.0.1:8000"
                  error={apiErrors.api_base_url?.message}
                  {...registerApi('api_base_url')}
                />
                <Input
                  label="WebSocket Base URL"
                  placeholder="ws://127.0.0.1:8000"
                  error={apiErrors.ws_base_url?.message}
                  {...registerApi('ws_base_url')}
                />
                <div className="grid grid-cols-2 gap-4">
                  <Input
                    label="Request Timeout (ms)"
                    type="number"
                    error={apiErrors.request_timeout?.message}
                    {...registerApi('request_timeout', { valueAsNumber: true })}
                  />
                </div>

                <div className="flex justify-end pt-4 border-t border-orbit-border-primary/50">
                  <Button type="submit" loading={saving === 'api'}>
                    <Save className="h-4 w-4 mr-2" />
                    Save API Settings
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* Connection Status */}
          <Card className="mt-6">
            <CardHeader>
              <CardTitle>Connection Status</CardTitle>
            </CardHeader>
            <CardContent>
              {healthLoading ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="p-4 bg-orbit-bg-tertiary/50 rounded-lg animate-pulse">
                      <div className="h-4 bg-orbit-bg-secondary rounded w-3/4 mb-2" />
                      <div className="h-3 bg-orbit-bg-secondary rounded w-1/2" />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { key: 'rest_api', label: 'REST API', value: healthStatus.rest_api },
                    { key: 'websocket', label: 'WebSocket', value: healthStatus.websocket },
                    { key: 'database', label: 'Database', value: healthStatus.database },
                    { key: 'ml_sandbox', label: 'ML Sandbox', value: healthStatus.ml_sandbox },
                  ].map(({ key, label, value }) => {
                    const { variant, label: statusLabel } = getStatusBadge(value);
                    return (
                      <div key={key} className="p-4 bg-orbit-bg-tertiary/50 rounded-lg">
                        <p className="text-orbit-text-tertiary text-sm">{label}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge variant={variant} size="sm">{statusLabel}</Badge>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabContent>

        {/* About Tab */}
        <TabContent value="about">
          <Card>
            <CardHeader>
              <CardTitle>About ORBIT</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="text-center py-8">
                <svg className="h-16 w-16 mx-auto text-orbit-accent-primary mb-4" viewBox="0 0 32 32" fill="none">
                  <circle cx="16" cy="16" r="12" stroke="currentColor" strokeWidth="2" fill="none" opacity="0.3" />
                  <circle cx="16" cy="16" r="8" stroke="currentColor" strokeWidth="2.5" fill="none" />
                  <ellipse cx="16" cy="16" rx="14" ry="4" stroke="currentColor" strokeWidth="1.5" fill="none" transform="rotate(-20 16 16)" opacity="0.5" />
                  <ellipse cx="16" cy="16" rx="14" ry="4" stroke="currentColor" strokeWidth="1.5" fill="none" transform="rotate(20 16 16)" opacity="0.5" />
                  <circle cx="16" cy="16" r="3" fill="currentColor" />
                </svg>
                <h2 className="text-2xl font-bold text-orbit-text-primary">ORBIT Mission Control</h2>
                <p className="text-orbit-text-secondary mt-2">Version 0.1.0</p>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="p-4 bg-orbit-bg-tertiary/50 rounded-lg">
                  <p className="text-orbit-text-tertiary">Frontend</p>
                  <p className="font-mono text-orbit-text-primary">React 18 + TypeScript + Vite</p>
                </div>
                <div className="p-4 bg-orbit-bg-tertiary/50 rounded-lg">
                  <p className="text-orbit-text-tertiary">Styling</p>
                  <p className="font-mono text-orbit-text-primary">Tailwind CSS</p>
                </div>
                <div className="p-4 bg-orbit-bg-tertiary/50 rounded-lg">
                  <p className="text-orbit-text-tertiary">State Management</p>
                  <p className="font-mono text-orbit-text-primary">Zustand</p>
                </div>
                <div className="p-4 bg-orbit-bg-tertiary/50 rounded-lg">
                  <p className="text-orbit-text-tertiary">Charts</p>
                  <p className="font-mono text-orbit-text-primary">Recharts</p>
                </div>
                <div className="p-4 bg-orbit-bg-tertiary/50 rounded-lg">
                  <p className="text-orbit-text-tertiary">Forms</p>
                  <p className="font-mono text-orbit-text-primary">React Hook Form + Zod</p>
                </div>
                <div className="p-4 bg-orbit-bg-tertiary/50 rounded-lg">
                  <p className="text-orbit-text-tertiary">Routing</p>
                  <p className="font-mono text-orbit-text-primary">React Router v6</p>
                </div>
                <div className="p-4 bg-orbit-bg-tertiary/50 rounded-lg">
                  <p className="text-orbit-text-tertiary">Real-time</p>
                  <p className="font-mono text-orbit-text-primary">WebSocket API</p>
                </div>
                <div className="p-4 bg-orbit-bg-tertiary/50 rounded-lg">
                  <p className="text-orbit-text-tertiary">Notifications</p>
                  <p className="font-mono text-orbit-text-primary">Sonner</p>
                </div>
              </div>

              <div className="pt-6 border-t border-orbit-border-primary/50">
                <h4 className="font-medium text-orbit-text-secondary mb-3">Links</h4>
                <div className="flex flex-wrap gap-4">
                  <Button variant="ghost" onClick={() => window.open('https://github.com', '_blank', 'noopener noreferrer')}>
                    GitHub Repository
                  </Button>
                  <Button variant="ghost" onClick={() => window.open('https://docs.orbit.local', '_blank', 'noopener noreferrer')}>
                    Documentation
                  </Button>
                  <Button variant="ghost" onClick={() => window.open('https://github.com/issues', '_blank', 'noopener noreferrer')}>
                    Report Issue
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabContent>
      </Tabs>
    </div>
  );
}
