export const WIDGET_PACKAGE_STATUS = "scaffold" as const;

export interface WidgetPackageInfo {
  readonly status: typeof WIDGET_PACKAGE_STATUS;
  readonly functional: false;
}

export function getWidgetPackageInfo(): WidgetPackageInfo {
  return { status: WIDGET_PACKAGE_STATUS, functional: false };
}
