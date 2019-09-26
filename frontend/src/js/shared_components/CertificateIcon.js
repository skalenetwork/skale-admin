import React from 'react'
import {Icon} from 'rmwc/Icon';


export default class CertificateIcon extends React.Component {

  getClass(value) {
    switch (value) {
      case 'added':
        return 'neon-green-icon';
      case 'inactive':
        return 'gray-round-icon';
      case 'expired':
        return 'orange-icon';
      default:
        return 'unknown';
    }
  }

  render() {
    return (
      <div className={"md-icon-wrap fl-center " + this.getClass(this.props.status)}>
        <Icon strategy="ligature" className="sm-icon">lock</Icon>
      </div>
    );
  }
}
