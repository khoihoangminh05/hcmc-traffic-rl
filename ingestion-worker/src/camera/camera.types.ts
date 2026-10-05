export type CameraMode = 'hls' | 'snapshot';

export interface CameraSource {
  cameraId: string;
  url: string;
  name?: string;
  /** hls = .m3u8 playlist; snapshot = JPEG poll (HCMC ImageHandler) */
  mode?: CameraMode;
}

export interface CameraCursor {
  lastSegmentUriByCamera: Record<string, string>;
  lastSuccessIsoByCamera: Record<string, string>;
}
