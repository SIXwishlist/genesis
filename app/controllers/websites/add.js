import Ember from 'ember';
import handleModelError from '../../utils/handle-model-error';


export default Ember.Controller.extend({
  breadCrumb: {name: 'New website', icon: 'globe'},
  queryParams: ['siteType'],
  siteType: null,
  confirmedSiteType: null,
  websiteOptions: {},
  selectedSiteType: function() {
    if (!this.get('siteTypes')) {
      return Ember.A();
    }
    return this.get('siteTypes').filterBy('id', this.get('siteType')).get('firstObject');
  }.property('siteType'),
  bumpWebsiteOptions: function() {
    return this.set('websiteOptions', this.get('confirmedSiteType.websiteOptions'));
  }.observes('confirmedSiteType'),
  canChooseDBType: function() {
    var dbe = this.get('confirmedSiteType.databaseEngines');
    return (dbe && dbe.get('length')>1);
  }.property('confirmedSiteType'),

  actions: {
    selectSiteType: function(siteType) {
      this.set('siteType', siteType.get('id'));
    },
    confirmSiteType: function() {
      this.set('confirmedSiteType', this.get('selectedSiteType'));
    },
    resetSiteType: function() {
      this.set('siteType', null);
      this.set('confirmedSiteType', null);
    },
    createWebsite: function() {
      var self = this;
      var extraData = {
        datadir: this.get("newSiteDataDir") || null,
        dbengine: this.get("canChooseDBType") ? (this.get("newSiteDBEngine.id") || this.get("availableDBTypes.firstObject.id")) : null
      };
      Ember.$('#new-website-form').form({
        fields: {
          name: ['regExp[/^[a-zA-Z0-9_]+$/]', 'empty'],
          port: ['integer[1..65536]', 'empty']
        },
        inline: true,
        keyboardShortcuts: false,
        onSuccess: function() {
          self.transitionToRoute("websites");
          ["text", "textarea", "password", "users", "boolean"].forEach(function(t) {
            if (!!self.get('websiteOptions.' + t)) {
              self.get('websiteOptions.' + t).forEach(function(i) {
                extraData[i.id] = extraData[i.value];
              });
            }
          });
          var site = self.store.createRecord('website', {
            id: self.get('newSiteName'),
            app: self.get('confirmedSiteType'),
            appName: self.get('confirmedSiteType.name'),
            icon: self.get('confirmedSiteType.icon'),
            domain: self.get('newSiteDomain') || self.get('domains.firstObject'),
            port: self.get('newSitePort'),
            extraData: extraData
          });
          var promise = site.save();
          promise.then(function(){}, function(e){
            handleModelError(self, e);
          });
        }
      });
      Ember.$('#new-website-form').form('validate form');
    }
  }
});
