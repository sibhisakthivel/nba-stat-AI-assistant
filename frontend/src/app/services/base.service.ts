import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export class BaseService {
  // protected baseUrl = 'http://localhost:8000/api';
  protected baseUrl = environment.apiUrl || 'http://localhost:8000/api';
  
  constructor(protected http: HttpClient) {}

  protected get(endpoint: string, params?: HttpParams): Observable<any> {
    return this.http.get(endpoint, { params });
  }

  protected post(endpoint: string, body: any, params?: HttpParams): Observable<any> {
    return this.http.post(endpoint, body, { params });
  }
}