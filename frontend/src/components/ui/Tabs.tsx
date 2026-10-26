// ORBIT Frontend - Tabs Component
// Accessible tabs with keyboard navigation

import { createContext, useContext, useState, ReactNode } from 'react';

interface TabsContextValue {
  value: string;
  onValueChange: (value: string) => void;
}

const TabsContext = createContext<TabsContextValue | null>(null);

export function Tabs({ children, defaultValue, value: controlledValue, onValueChange }: {
  children: ReactNode;
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
}) {
  const [uncontrolledValue, setUncontrolledValue] = useState(defaultValue || '');
  const isControlled = controlledValue !== undefined;
  const value = isControlled ? controlledValue : uncontrolledValue;

  const handleValueChange = (newValue: string) => {
    if (!isControlled) {
      setUncontrolledValue(newValue);
    }
    onValueChange?.(newValue);
  };

  return (
    <TabsContext.Provider value={{ value, onValueChange: handleValueChange }}>
      <div data-orbit-tabs>{children}</div>
    </TabsContext.Provider>
  );
}

export function TabList({ children, className = '', ...props }: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      role="tablist"
      className={`flex gap-1 bg-orbit-bg-tertiary p-1 rounded-lg border border-orbit-border-primary ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function TabTrigger({ value, children, className = '', disabled = false, ...props }: {
  value: string;
  children: ReactNode;
  className?: string;
  disabled?: boolean;
}) {
  const context = useContext(TabsContext);
  if (!context) {
    throw new Error('TabTrigger must be used within Tabs');
  }

  const { value: currentValue, onValueChange } = context;
  const isActive = currentValue === value;

  return (
    <button
      role="tab"
      aria-selected={isActive}
      aria-disabled={disabled}
      disabled={disabled}
      onClick={() => !disabled && onValueChange(value)}
      className={`
        flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-all duration-150
        focus-ring
        ${isActive
          ? 'bg-orbit-bg-card text-orbit-text-primary shadow-sm border border-orbit-border-primary'
          : 'text-orbit-text-secondary hover:text-orbit-text-primary hover:bg-orbit-bg-card/50'}
        ${disabled ? 'opacity-50 pointer-events-none' : ''}
        ${className}
      `}
      {...props}
    >
      {children}
    </button>
  );
}

export function TabContent({ value, children, className = '', ...props }: {
  value: string;
  children: ReactNode;
  className?: string;
}) {
  const context = useContext(TabsContext);
  if (!context) {
    throw new Error('TabContent must be used within Tabs');
  }

  const { value: currentValue } = context;
  const isActive = currentValue === value;

  if (!isActive) return null;

  return (
    <div
      role="tabpanel"
      className={`${className}`}
      {...props}
    >
      {children}
    </div>
  );
}