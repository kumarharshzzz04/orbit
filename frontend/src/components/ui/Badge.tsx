// ORBIT Frontend - Badge Component
// Status badges and labels

import { HTMLAttributes, forwardRef } from 'react';

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'keep' | 'reject' | 'pending' | 'running' | 'completed' | 'failed' | 'info' | 'warning';
  size?: 'sm' | 'md' | 'lg';
  dot?: boolean;
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ children, variant = 'default', size = 'md', dot = false, className = '', ...props }, ref) => {
    const variantClasses = {
      default: 'bg-orbit-bg-tertiary text-orbit-text-secondary border border-orbit-border-primary',
      keep: 'bg-green-500/20 text-green-400 border border-green-500/30',
      reject: 'bg-red-500/20 text-red-400 border border-red-500/30',
      pending: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
      running: 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 animate-pulse',
      completed: 'bg-green-500/20 text-green-400 border border-green-500/30',
      failed: 'bg-red-500/20 text-red-400 border border-red-500/30',
      info: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
      warning: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
    };

    const sizeClasses = {
      sm: 'px-2 py-0.5 text-xs',
      md: 'px-2.5 py-0.5 text-xs',
      lg: 'px-3 py-1 text-sm',
    };

    const dotColors = {
      default: 'bg-orbit-text-tertiary',
      keep: 'bg-green-400',
      reject: 'bg-red-400',
      pending: 'bg-amber-400',
      running: 'bg-cyan-400 animate-pulse',
      completed: 'bg-green-400',
      failed: 'bg-red-400',
      info: 'bg-blue-400',
      warning: 'bg-amber-400',
    };

    return (
      <span
        ref={ref}
        className={`inline-flex items-center gap-1.5 rounded-full font-medium border ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
        {...props}
      >
        {dot && <span className={`status-dot ${variant} ${dotColors[variant]}`} aria-hidden="true" />}
        {children}
      </span>
    );
  }
);

Badge.displayName = 'Badge';

// Status-specific badges for convenience
export const StatusBadge = ({ status, ...props }: { status: string } & Omit<BadgeProps, 'variant'>) => {
  const variantMap: Record<string, BadgeProps['variant']> = {
    KEEP: 'keep',
    REJECT: 'reject',
    PENDING: 'pending',
    RUNNING: 'running',
    COMPLETED: 'completed',
    FAILED: 'failed',
    CANCELLED: 'reject',
    pending: 'pending',
    running: 'running',
    completed: 'completed',
    failed: 'failed',
    proposed: 'pending',
    approved: 'keep',
    vetoed: 'reject',
  };

  return <Badge variant={variantMap[status] || 'default'} dot {...props}>{status}</Badge>;
};