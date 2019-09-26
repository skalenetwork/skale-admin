import React from 'react';
import ReactDOM from 'react-dom';
import {HashRouter} from 'react-router-dom'
import registerServiceWorker from './registerServiceWorker';

import App from './App';

import 'bootstrap/dist/css/bootstrap.css';
import 'material-components-web/dist/material-components-web.min.css';

import '../stylesheets/index.scss';

ReactDOM.render(
  <HashRouter>
    <App/>
  </HashRouter>,
  document.getElementById('root'));

registerServiceWorker();
